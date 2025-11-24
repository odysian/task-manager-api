from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Literal
from datetime import datetime, date
from collections import Counter
from sqlalchemy.orm import Session

from models import Task, TaskCreate, TaskUpdate, TaskStats, BulkTaskUpdate
from db_config import get_db
import db_models

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)


# --- Endpoints ---

@router.get("", response_model=list[Task])
def get_all_tasks(
    db_session: Session = Depends(get_db),
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
    # Start with base query
    query = db_session.query(db_models.Task)

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

    return tasks


@router.get("/stats", response_model=TaskStats)
def get_task_stats(db_session: Session = Depends(get_db)):
    """Get statistics about all tasks"""

    all_tasks: list[db_models.Task] = db_session.query(db_models.Task).all()
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
    
    
    return {
        "total": total,
        "completed": completed,
        "incomplete": incomplete,
        "by_priority": dict(by_priority),
        "by_tag": dict(by_tag),
        "overdue": overdue
    }


@router.patch("/bulk", response_model=list[Task])
def bulk_update_tasks(bulk_data: BulkTaskUpdate, db_session: Session = Depends(get_db)):
    """Update multiple tasks at once"""

    # Get the updates to apply
    update_data = bulk_data.updates.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    
    # Query all tasks with the given IDs
    tasks = db_session.query(db_models.Task).filter(
        db_models.Task.id.in_(bulk_data.task_ids)
    ).all()

    # Check if all IDs were found
    found_ids = {task.id for task in tasks}
    missing_ids = [task_id for task_id in bulk_data.task_ids if task_id not in found_ids]

    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Tasks not found: {missing_ids}")
    

    # Update each task
    for task in tasks:
        for field, value in update_data.items():
            setattr(task, field, value)

    db_session.commit()

    for task in tasks: db_session.refresh(task)
    
    return tasks


@router.get("/{task_id}", response_model=Task)
def get_task_id(task_id: int, db_session: Session = Depends(get_db)):
    """Retrieve a single task by ID"""
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")
    
    return task


@router.post("", status_code=201, response_model=Task)
def create_task(task_data: TaskCreate, db_session: Session = Depends(get_db)):
    """Create a new task"""
    

    new_task = db_models.Task(
        title=task_data.title,
        description=task_data.description,
        completed=False,
        priority=task_data.priority,
        due_date=task_data.due_date,
        tags=task_data.tags
    )
    db_session.add(new_task)
    db_session.commit()
    db_session.refresh(new_task)

    return new_task


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, task_data: TaskUpdate, db_session: Session = Depends(get_db)):
    """Update a task"""
    # Find the task
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")

    # Get only the fields that were provided
    update_data = task_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    # Update the task
    for field, value in update_data.items():
        setattr(task, field, value)

    db_session.commit()
    db_session.refresh(task)

    return task
    


@router.delete("/{task_id}", status_code=204)
def delete_task_id(task_id: int, db_session: Session = Depends(get_db)):
    """Delete a task by ID"""

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")

    db_session.delete(task)
    db_session.commit()

    return None


@router.post("/{task_id}/tags", response_model=Task)
def add_tags(task_id: int, tags: list[str], db_session: Session = Depends(get_db)):
    """Add tags to a task without removing existing tags"""
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")
    
    # Add new tags, avoiding duplicates
    for tag in tags:
        if tag not in task.tags:
            task.tags.append(tag)

    # Mark the tags field as modified (PostgreSQL array needs this)
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "tags")

    db_session.commit()
    db_session.refresh(task)

    return task


@router.delete("/{task_id}/tags/{tag}", response_model=Task)
def remove_tag(task_id: int, tag: str, db_session: Session = Depends(get_db)):
    """Remove a specific tag from a task"""
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")

    if tag not in task.tags:
        raise HTTPException(status_code=404, detail=f"Tag '{tag}' not found on this task")
        
    task.tags.remove(tag)

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "tags")

    db_session.commit()
    db_session.refresh(task)

    return task

