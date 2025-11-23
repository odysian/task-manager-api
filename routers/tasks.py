from fastapi import APIRouter, HTTPException, Query 
from typing import Optional, Literal

from models import Task, TaskCreate, TaskUpdate
import database as db

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)


# --- Endpoints ---

@router.get("", response_model=list[Task])
def get_all_tasks(
    completed: Optional[bool] = None,
    priority: Optional[Literal["low", "medium", "high"]] = None,
    search: Optional[str] = None,
    sort_by: Optional[Literal["id", "title", "priority", "completed"]] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100)
):

    """Retrieve all tasks with optional filtering"""
    result = db.tasks

    # Filter by completion status
    if completed is not None:
        result = [t for t in result if t["completed"] == completed]

    if priority is not None:
        result = [t for t in result if t["priority"] == priority]

    # Filter by title search
    if search:
        search_lower = search.lower()
        result = [t for t in result if search_lower in t["title"].lower()
                  or (t["description"] and search_lower in t["description"].lower())]

    if sort_by:
        if sort_by == "priority":
            # Custom sort order: high > medium > low
            priority_order = {"high": 0, "medium": 1, "low": 2}
            result = sorted(result, key=lambda t: priority_order[t["priority"]])
        else:
            # For other fields, sort directly
            result = sorted(result, key=lambda t: t[sort_by])

    # Apply limit
    return result[skip:skip + limit]


@router.get("/{task_id}", response_model=Task)
def get_task_id(task_id: int):
    """Retrieve a single task by ID"""

    return db.get_task_by_id(task_id)


@router.post("/tasks", status_code=201, response_model=Task)
def create_task(task_data: TaskCreate):
    """Create a new task"""
    global task_id_counter
    db.task_id_counter += 1

    task = {
        "id": db.task_id_counter,
        "title": task_data.title,
        "description": task_data.description,
        "completed": False,
        "priority": task_data.priority
    }
    db.tasks.append(task)
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, task_data: TaskUpdate):
    """Update task completion"""

    task = db.get_task_by_id(task_id)

    # Check if any fields were provided
    update_data = task_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )

    # Update data with provided fields
    task.update(update_data)

    return task
    


@router.delete("{task_id}", status_code=204)
def delete_task_id(task_id: int):
    """Delete a task by ID"""

    task = db.get_task_by_id(task_id)
    db.tasks.remove(task)