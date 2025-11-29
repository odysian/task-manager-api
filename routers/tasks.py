import logging
from fastapi import APIRouter, HTTPException, Query, Depends, status, BackgroundTasks
from typing import Optional, Literal
from datetime import datetime, date
from collections import Counter
from sqlalchemy.orm import Session
from models import Task, TaskCreate, TaskUpdate, TaskStats, BulkTaskUpdate
from db_config import get_db
import db_models
import exceptions
from dependencies import get_current_user
from background_tasks import send_task_completion_notification, cleanup_after_task_deletion

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)
logger = logging.getLogger(__name__)


# --- Endpoints ---

@router.get("", response_model=list[Task])
def get_all_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
    completed: Optional[bool] = None,
    priority: Optional[Literal["low", "medium", "high"]] = None,
    tag: Optional[str] = None,
    overdue: Optional[bool] = None,
    search: Optional[str] = None,
    created_after: Optional[date] = None,
    created_before: Optional[date] = None,
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
    if tag is not None:
        query = query.filter(db_models.Task.tags.contains([tag]))

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

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    tasks = query.all()

    logger.info(f"Successfully retrieved {len(tasks)} tasks for user_id={current_user.id}")
    return tasks


@router.get("/stats", response_model=TaskStats)
def get_task_stats(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Get statistics about all tasks"""
    logger.info(f"Retrieving task statistics for user_id={current_user.id}")

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

    return {
        "total": total,
        "completed": completed,
        "incomplete": incomplete,
        "by_priority": dict(by_priority),
        "by_tag": dict(by_tag),
        "overdue": overdue
    }


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
        db_models.Task.user_id == current_user.id,
        db_models.Task.id.in_(bulk_data.task_ids)
    ).all() # type: ignore

    # Check if all IDs were found
    found_ids = {task.id for task in tasks}
    missing_ids = [task_id for task_id in bulk_data.task_ids if task_id not in found_ids]

    logger.info(f"Bulk update for user_id={current_user.id}: {len(found_ids)} tasks, updates={bulk_data}")

    if missing_ids:
        logger.warning(f"Bulk update: some tasks not found or unauthorized: missing_ids={missing_ids}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tasks not found: {missing_ids}")
    
    # Update each task
    for task in tasks:
        for field, value in update_data.items():
            setattr(task, field, value)

    db_session.commit()

    logger.info(f"Bulk update completed: {len(tasks)} tasks updated for user_id={current_user.id}")

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
    
    # Check if task belongs to current user
    if task.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access task_id={task_id} owned by user_id={task.user_id}")
        raise exceptions.UnauthorizedTaskAccessError(
            task_id=task_id,
            user_id=current_user.id # type: ignore
        )
    
    logger.info(f"Task retrieved successfully: task_id={task_id}, user_id={current_user.id}")
    return task


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Task)
def create_task(
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

    # Check if task belongs to current user
    if task.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access task_id={task_id} owned by user_id={task.user_id}")
        raise exceptions.UnauthorizedTaskAccessError(
            task_id=task_id,
            user_id=current_user.id # type: ignore
        )
    
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

        # Check if task belongs to current user
    if task.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized delete attempt: user_id={current_user.id} tried to delete task_id={task_id}")
        raise exceptions.UnauthorizedTaskAccessError(
            task_id=task_id,
            user_id=current_user.id # type: ignore
        )

    task_title = task.title

    db_session.delete(task)
    db_session.commit()

    background_tasks.add_task(
        cleanup_after_task_deletion,
        task_id=task.id, # type: ignore
        task_title=task.title # type: ignore
    )
    logger.info(f"Task deleted successfully: task_id={task_id}, user_id={current_user.id}")

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
    
    # Check if task belongs to current user
    if task.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access task_id={task_id} owned by user_id={task.user_id}")
        raise exceptions.UnauthorizedTaskAccessError(
            task_id=task_id,
            user_id=current_user.id # type: ignore
        )

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

    # Check if task belongs to current user
    if task.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access task_id={task_id} owned by user_id={task.user_id}")
        raise exceptions.UnauthorizedTaskAccessError(
            task_id=task_id,
            user_id=current_user.id # type: ignore
        )

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