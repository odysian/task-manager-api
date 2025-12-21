import json
import logging
import time
from collections import Counter
from datetime import date, datetime
from typing import Any, Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

import db_models
from core import exceptions
from core.rate_limit_config import limiter
from core.redis_config import get_cache, invalidate_user_cache, set_cache
from db_config import get_db
from dependencies import TaskPermission, get_current_user, require_task_access
from schemas.task import (
    BulkTaskUpdate,
    PaginatedTasks,
    Task,
    TaskCreate,
    TaskStats,
    TaskUpdate,
)
from services import activity_service
from services.background_tasks import cleanup_after_task_deletion, notify_task_completed

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)


def serialize_value(value: Any) -> Any:
    """Convert non-JSON serializable types to JSON-compatible formats."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}

    return value


# --- Endpoints ---


@router.get("", response_model=PaginatedTasks)
def get_all_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
    completed: Optional[bool] = None,
    priority: Optional[Literal["low", "medium", "high"]] = None,
    tags: Optional[str] = Query(
        default=None,
        description="Comma seperated list of tags. Tasks must contain ALL listed tags",
    ),
    overdue: Optional[bool] = None,
    search: Optional[str] = None,
    created_after: Optional[date] = None,
    created_before: Optional[date] = None,
    due_after: Optional[date] = None,
    due_before: Optional[date] = None,
    sort_by: Optional[
        Literal["id", "title", "priority", "completed", "created_at", "due_date"]
    ] = None,
    sort_order: Literal["asc", "desc"] = "asc",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    """Retrieve all tasks with optional filtering"""
    logger.info(f"Retrieving all tasks for user_id={current_user.id}")

    # Start with base query
    query = db_session.query(db_models.Task).filter(
        db_models.Task.user_id == current_user.id
    )

    # Completion and priority filters
    if completed is not None:
        query = query.filter(db_models.Task.completed == completed)

    if priority is not None:
        query = query.filter(db_models.Task.priority == priority)

    # Tag filter
    if tags:
        # Split by comma, then strip whitespace
        tag_list = [tag.strip() for tag in tags.split(",")]
        # Filter out empty strings
        tag_list = [t for t in tag_list if t]
        query = query.filter(db_models.Task.tags.contains(tag_list))

    # Title and description filters
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.filter(
            (db_models.Task.title.ilike(search_pattern))
            | (db_models.Task.description.ilike(search_pattern))
        )

    # Date filters
    if created_after:
        query = query.filter(db_models.Task.created_at >= created_after)

    if created_before:
        query = query.filter(db_models.Task.created_at <= created_before)

    if due_after:
        query = query.filter(db_models.Task.due_date >= due_after)

    if due_before:
        query = query.filter(db_models.Task.due_date <= due_before)

    # Overdue filter
    if overdue:
        today = date.today()
        if overdue:
            query = query.filter(
                db_models.Task.due_date.isnot(None),
                db_models.Task.completed.is_(False),
                db_models.Task.due_date < today,
            )
        else:
            query = query.filter(
                (db_models.Task.due_date.is_(None))
                | (db_models.Task.completed.is_(True))
                | (db_models.Task.due_date >= today)
            )

    # Apply sorting
    if sort_by:
        sort_column = getattr(db_models.Task, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column)

    total_count = query.count()

    # Apply pagination
    tasks = query.offset(skip).limit(limit).all()

    logger.info(
        f"Successfully retrieved {len(tasks)} tasks for user_id={current_user.id}"
    )
    return {
        "tasks": tasks,
        "total": total_count,
        "page": skip // limit + 1,
        "pages": (total_count + limit - 1) // limit,
    }


@router.get("/stats", response_model=TaskStats)
def get_task_stats(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Get statistics about all tasks with Redis caching"""
    start_time = time.time()
    logger.info(f"Retrieving task statistics for user_id={current_user.id}")

    cache_key = f"stats:user_{current_user.id}"
    cached_stats = get_cache(cache_key)

    if cached_stats:
        # Cache hit - Return cached data
        stats_dict = json.loads(cached_stats)
        elapsed_time = (time.time() - start_time) * 1000
        logger.info(
            f"Returning cached statistics for user_id={current_user.id} "
            f"| Time: {elapsed_time:.2f}ms"
        )
        return stats_dict

    # Cache miss - calculate stats from database
    logger.info(f"Calculating fresh statistics for user_id={current_user.id}")

    all_tasks: list[db_models.Task] = (
        db_session.query(db_models.Task)
        .filter(db_models.Task.user_id == current_user.id)
        .all()
    )

    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.completed is True)
    incomplete = total - completed

    # Count by priority
    by_priority = Counter(t.priority for t in all_tasks)

    # Count by tag (each tag counted seperately)
    all_tags = []
    for task in all_tasks:
        all_tags.extend(task.tags)  # type: ignore[arg-type]
    by_tag = Counter(all_tags)

    # Count overdue tasks
    today = date.today()
    overdue = sum(
        1
        for t in all_tasks
        if t.due_date is not None  # type: ignore[arg-type]
        and not t.completed  # type: ignore[arg-type]
        and t.due_date < today
    )

    tasks_shared = (
        db_session.query(func.count(distinct(db_models.TaskShare.task_id)))
        .filter(db_models.TaskShare.shared_by_user_id == current_user.id)
        .scalar()
    )

    comments_posted = (
        db_session.query(db_models.TaskComment)
        .filter(db_models.TaskComment.user_id == current_user.id)
        .count()
    )

    logger.info(f"Successfully retrieved task statistics for user_id={current_user.id}")

    stats_dict = {
        "total": total,
        "completed": completed,
        "incomplete": incomplete,
        "by_priority": dict(by_priority),
        "by_tag": dict(by_tag),
        "overdue": overdue,
        "tasks_shared": tasks_shared,
        "comments_posted": comments_posted,
    }

    # Store in cache for next time
    set_cache(cache_key, json.dumps(stats_dict))

    elapsed_time = (time.time() - start_time) * 1000
    logger.info(
        f"Successfully calculated and cached statistics for "
        f"user_id={current_user.id} | Time: {elapsed_time:.2f}ms"
    )

    return stats_dict


@router.patch("/bulk", response_model=list[Task])
def bulk_update_tasks(
    bulk_data: BulkTaskUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Update multiple tasks at once"""

    # Get the updates to apply
    update_data = bulk_data.updates.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    # Query all tasks with the given IDs

    tasks = (
        db_session.query(db_models.Task)
        .filter(db_models.Task.id.in_(bulk_data.task_ids))
        .all()
    )

    # Check if all IDs were found
    found_ids = {task.id for task in tasks}
    missing_ids = [
        task_id for task_id in bulk_data.task_ids if task_id not in found_ids
    ]

    logger.info(
        f"Bulk update for user_id={current_user.id}: {len(found_ids)} tasks, updates={bulk_data}"
    )

    if missing_ids:
        logger.warning(
            f"Bulk update: some tasks not found or unauthorized: missing_ids={missing_ids}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tasks not found: {missing_ids}",
        )

    for task in tasks:
        require_task_access(task, current_user, db_session, TaskPermission.EDIT)

    logger.info(
        f"Bulk update authorized for user_id{current_user.id} on {len(tasks)} tasks"
    )

    # Update each task
    for task in tasks:
        for field, value in update_data.items():
            setattr(task, field, value)

    db_session.commit()

    logger.info(
        f"Bulk update completed: {len(tasks)} tasks updated for user_id={current_user.id}"
    )

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id)  # type: ignore

    for task in tasks:
        db_session.refresh(task)

    return tasks


@router.get("/{task_id}", response_model=Task)
def get_task_id(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Retrieve a single task by ID"""

    logger.info(f"Fetching task_id={task_id} for user_id={current_user.id}")

    task = (
        db_session.query(db_models.Task)
        .options(selectinload(db_models.Task.shares))  # ← ADD THIS
        .filter(db_models.Task.id == task_id)
        .first()
    )

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.VIEW)

    logger.info(
        f"Task retrieved successfully: task_id={task_id}, user_id={current_user.id}"
    )
    return task


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Task)
@limiter.limit("100/hour")  # 100 tasks per hour
def create_task(
    request: Request,  # pylint: disable=unused-argument
    task_data: TaskCreate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Create a new task"""

    logger.info(
        f"Creating task for user_id={current_user.id}: title='{task_data.title}'"
    )

    new_task = db_models.Task(
        title=task_data.title,
        description=task_data.description,
        completed=task_data.completed,
        priority=task_data.priority,
        due_date=task_data.due_date,
        tags=task_data.tags,
        user_id=current_user.id,
    )
    db_session.add(new_task)
    db_session.flush()
    activity_service.log_task_created(
        db_session=db_session, user_id=current_user.id, task=new_task  # type: ignore
    )
    db_session.commit()
    db_session.refresh(new_task)

    logger.info(
        f"Task created successfully: task_id={new_task.id}, user_id={current_user.id}"
    )

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id)  # type: ignore

    return new_task


@router.patch("/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Update a task"""
    logger.info(f"Updating task for user_id={current_user.id}: task_id={task_id}")

    # Find the task
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.EDIT)

    # Get only the fields that were provided
    update_data = task_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    old_values = {}
    for field in update_data.keys():
        old_values[field] = serialize_value(getattr(task, field))

    # Check if task is being marked as complete for first time
    was_incomplete = not task.completed  # type: ignore
    is_being_marked_complete = update_data.get("completed") is True

    # Update the task
    for field, value in update_data.items():
        setattr(task, field, value)

    new_values = {}
    for field in update_data.keys():
        new_values[field] = serialize_value(getattr(task, field))

    activity_service.log_task_updated(
        db_session=db_session,
        user_id=current_user.id,  # type: ignore
        task=task,
        old_values=old_values,
        new_values=new_values,
    )

    db_session.commit()
    db_session.refresh(task)

    # Only send notification when task transitions from incomplete -> complete
    if was_incomplete and is_being_marked_complete:
        logger.info(f"Task completed, scheduling notification: task_id={task_id}")
        # If I am NOT the owner, notify the owner
        if task.user_id != current_user.id:  # type: ignore
            background_tasks.add_task(
                notify_task_completed,
                recipient_user_id=task.user_id,  # type: ignore
                recipient_email=task.owner.email,
                task_title=task.title,  # type: ignore
                completer_username=current_user.username,  # type: ignore
            )

    logger.info(
        f"Task updates successfully: task_id={task_id}, user_id={current_user.id}"
    )

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id)  # type: ignore

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_id(
    task_id: int,
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Delete a task by ID"""

    logger.info(f"Deleting task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Delete failed: task_id={task_id} not found")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.OWNER)

    # Save task info before deletion
    task_title: str = task.title  # type: ignore

    # Get list of files to delete from disk
    file_list = [file.stored_filename for file in task.files]

    activity_service.log_task_deleted(
        db_session=db_session, user_id=current_user.id, task=task  # type: ignore
    )

    db_session.delete(task)
    db_session.commit()

    background_tasks.add_task(
        cleanup_after_task_deletion,
        task_id=task.id,  # type: ignore
        task_title=task_title,  # type: ignore
        file_list=file_list,
    )
    logger.info(
        f"Task deleted successfully: task_id={task_id}, user_id={current_user.id}"
    )

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id)  # type: ignore


@router.post("/{task_id}/tags", response_model=Task)
def add_tags(
    task_id: int,
    tags: list[str],
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Add tags to a task without removing existing tags"""
    logger.info(f"Adding tags for task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.EDIT)

    # Add new tags, avoiding duplicates
    for tag in tags:
        if tag not in task.tags:
            task.tags.append(tag)

    # Mark the tags field as modified (PostgreSQL array needs this)
    flag_modified(task, "tags")

    db_session.commit()
    db_session.refresh(task)

    logger.info(
        f"Successfully added {len(tags)} tags for task_id={task_id}, user_id={current_user.id}"
    )

    return task


@router.delete("/{task_id}/tags/{tag}", response_model=Task)
def remove_tag(
    task_id: int,
    tag: str,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Remove a specific tag from a task"""
    logger.info(f"Removing tag for task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.EDIT)

    if tag not in task.tags:
        logger.warning(f"Tag not found: {tag} in task_id={task_id}")
        raise exceptions.TagNotFoundError(task_id=task_id, tag=tag)

    task.tags.remove(tag)

    flag_modified(task, "tags")

    db_session.commit()
    db_session.refresh(task)

    return task
