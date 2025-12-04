import logging
from fastapi import APIRouter, HTTPException, Query, Depends, status, BackgroundTasks, Request
from typing import Optional, Literal
from datetime import datetime, date
from collections import Counter
from sqlalchemy.orm import Session
import json
import time
from models import Task, TaskCreate, TaskUpdate, TaskStats, BulkTaskUpdate, PaginatedTasks
from db_config import get_db
import db_models
import exceptions
from dependencies import get_current_user, require_task_access, TaskPermission
from background_tasks import send_task_completion_notification, cleanup_after_task_deletion
from redis_config import get_cache, set_cache, invalidate_user_cache
from rate_limit_config import limiter

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)
logger = logging.getLogger(__name__)


# --- Endpoints ---

@router.get("", response_model=PaginatedTasks)
def get_all_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
    completed: Optional[bool] = None,
    priority: Optional[Literal["low", "medium", "high"]] = None,
    tags: Optional[str] = Query(
        default=None,
        description="Comma seperated list of tags. Tasks must contain ALL listed tags"
    ),
    overdue: Optional[bool] = None,
    search: Optional[str] = None,
    created_after: Optional[date] = None,
    created_before: Optional[date] = None,
    due_after: Optional[date] = None,
    due_before: Optional[date] = None,
    sort_by: Optional[Literal["id", "title", "priority", "completed", "created_at", "due_date"]] = None,
    sort_order: Literal["asc", "desc"] = "asc",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100)
):

    """Retrieve all tasks with optional filtering"""
    logger.info(f"Retrieving all tasks for user_id={current_user.id}")

    # Start with base query
    query = db_session.query(db_models.Task).filter(db_models.Task.user_id == current_user.id)

    # Completion and priority filters
    if completed is not None:
        query = query.filter(db_models.Task.completed == completed)

    if priority is not None:
        query = query.filter(db_models.Task.priority == priority)

    # Tag filter
    if tags:
        # Split by comma, then strip whitespace
        tag_list = [tag.strip() for tag in tags.split(',')]
        # Filter out empty strings
        tag_list = [t for t in tag_list if t]
        query = query.filter(db_models.Task.tags.contains(tag_list))

    # Title and description filters
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.filter(
            (db_models.Task.title.ilike(search_pattern)) |
            (db_models.Task.description.ilike(search_pattern))
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
                db_models.Task.completed == False,
                db_models.Task.due_date < today
            )
        else:
            query = query.filter(
                (db_models.Task.due_date.is_(None)) |
                (db_models.Task.completed == True) | 
                (db_models.Task.due_date >= today)
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

    logger.info(f"Successfully retrieved {len(tasks)} tasks for user_id={current_user.id}")
    return {
        "tasks": tasks,
        "total": total_count,
        "page": skip // limit + 1,
        "pages": (total_count + limit - 1) // limit
    }

@router.get("/stats", response_model=TaskStats)
def get_task_stats(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
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
        logger.info(f"Returning cached statistics for user_id={current_user.id} | Time: {elapsed_time:.2f}ms")
        return stats_dict
    
    # Cache miss - calculate stats from database
    logger.info(f"Calculating fresh statistics for user_id={current_user.id}")

    all_tasks: list[db_models.Task] = db_session.query(db_models.Task).filter(
        db_models.Task.user_id == current_user.id
    ).all()


    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.completed is True)
    incomplete = total - completed

    # Count by priority
    by_priority = Counter(t.priority for t in all_tasks)

    # Count by tag (each tag counted seperately)
    all_tags = []
    for task in all_tasks:
        all_tags.extend(task.tags) # type: ignore[arg-type]
    by_tag = Counter(all_tags)

    # Count overdue tasks
    today = date.today()
    overdue = sum( 
        1 for t in all_tasks 
        if t.due_date is not None # type: ignore[arg-type]
        and not t.completed # type: ignore[arg-type]
        and t.due_date < today
    )
    
    logger.info(f"Successfully retrieved task statistics for user_id={current_user.id}")

    stats_dict = {
        "total": total,
        "completed": completed,
        "incomplete": incomplete,
        "by_priority": dict(by_priority),
        "by_tag": dict(by_tag),
        "overdue": overdue
    }

    # Store in cache for next time
    set_cache(cache_key, json.dumps(stats_dict))

    elapsed_time = (time.time() - start_time) * 1000
    logger.info(f"Successfully calculated and cached statistics for user_id={current_user.id} | Time: {elapsed_time:.2f}ms")

    return stats_dict


@router.patch("/bulk", response_model=list[Task])
def bulk_update_tasks(
    bulk_data: BulkTaskUpdate, 
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Update multiple tasks at once"""

    # Get the updates to apply
    update_data = bulk_data.updates.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    
    # Query all tasks with the given IDs

    tasks = db_session.query(db_models.Task).filter(
        db_models.Task.id.in_(bulk_data.task_ids)
    ).all() 

    # Check if all IDs were found
    found_ids = {task.id for task in tasks}
    missing_ids = [task_id for task_id in bulk_data.task_ids if task_id not in found_ids]

    logger.info(f"Bulk update for user_id={current_user.id}: {len(found_ids)} tasks, updates={bulk_data}")

    if missing_ids:
        logger.warning(f"Bulk update: some tasks not found or unauthorized: missing_ids={missing_ids}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tasks not found: {missing_ids}")
    
    for task in tasks:
        require_task_access(task, current_user, db_session, TaskPermission.EDIT)

    logger.info(f"Bulk update authorized for user_id{current_user.id} on {len(tasks)} tasks")

    # Update each task
    for task in tasks:
        for field, value in update_data.items():
            setattr(task, field, value)

    db_session.commit()

    logger.info(f"Bulk update completed: {len(tasks)} tasks updated for user_id={current_user.id}")

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id) # type: ignore

    for task in tasks: db_session.refresh(task)
    
    return tasks


@router.get("/{task_id}", response_model=Task)
def get_task_id(
    task_id: int, 
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Retrieve a single task by ID"""

    logger.info(f"Fetching task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id) # Custom Exception
    
    require_task_access(task, current_user, db_session, TaskPermission.VIEW)

    logger.info(f"Task retrieved successfully: task_id={task_id}, user_id={current_user.id}")
    return task


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Task)
@limiter.limit("100/hour") # 100 tasks per hour
def create_task(
    request: Request,
    task_data: TaskCreate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Create a new task"""
    
    logger.info(f"Creating task for user_id={current_user.id}: title='{task_data.title}'")

    new_task = db_models.Task(
        title=task_data.title,
        description=task_data.description,
        completed=task_data.completed,
        priority=task_data.priority,
        due_date=task_data.due_date,
        tags=task_data.tags,
        user_id=current_user.id
    )
    db_session.add(new_task)
    db_session.commit()
    db_session.refresh(new_task)

    logger.info(f"Task created successfully: task_id={new_task.id}, user_id={current_user.id}")

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id) # type: ignore

    return new_task


@router.patch("/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")


    # Check if task is being marked as complete for first time
    was_incomplete = not task.completed # type: ignore
    is_being_marked_complete = update_data.get("completed") is True

    # Update the task
    for field, value in update_data.items():
        setattr(task, field, value)

    db_session.commit()
    db_session.refresh(task)

    # Only send notification when task transitions from incomplete -> complete
    if was_incomplete and is_being_marked_complete:
        logger.info(f"Task completed, scheduling notification: task_id={task_id}")
        background_tasks.add_task(
            send_task_completion_notification,
            user_email=current_user.email, # type: ignore
            task_title=task.title, # type: ignore
            task_id=task.id # type: ignore
        )

    logger.info(f"Task updates successfully: task_id={task_id}, user_id={current_user.id}")

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id) # type: ignore

    return task
    

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_id(
    task_id: int,
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)    
):
    """Delete a task by ID"""

    logger.info(f"Deleting task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()
    
    if not task:
        logger.warning(f"Delete failed: task_id={task_id} not found")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.OWNER)

    # Save task info before deletion
    task_title: str = task.title # type: ignore

    # Get list of files to delete from disk
    file_list = [file.stored_filename for file in task.files]

    db_session.delete(task)
    db_session.commit()

    background_tasks.add_task(
        cleanup_after_task_deletion,
        task_id=task.id, # type: ignore
        task_title=task.title, # type: ignore
        file_list=file_list 

    )
    logger.info(f"Task deleted successfully: task_id={task_id}, user_id={current_user.id}")

    # Invalidate stats cache since task count changed
    invalidate_user_cache(current_user.id) # type: ignore

    return None


@router.post("/{task_id}/tags", response_model=Task)
def add_tags(
    task_id: int,
    tags: list[str],
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)    
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
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "tags")

    db_session.commit()
    db_session.refresh(task)

    logger.info(f"Successfully added {len(tags)} tags for task_id={task_id}, user_id={current_user.id}")

    return task


@router.delete("/{task_id}/tags/{tag}", response_model=Task)
def remove_tag(
    task_id: int,
    tag: str, db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)    
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
        raise exceptions.TagNotFoundError(
            task_id=task_id,
            tag=tag
        )
        
    task.tags.remove(tag)

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "tags")

    db_session.commit()
    db_session.refresh(task)

    return task