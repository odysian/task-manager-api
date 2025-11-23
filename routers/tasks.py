from fastapi import APIRouter, HTTPException, Query 
from typing import Optional

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
    search: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100)
):

    """Retrieve all tasks with optional filtering"""
    result = db.tasks

    # Filter by completion status
    if completed is not None:
        result = [t for t in result if t["completed"] == completed]

    # Filter by title search
    # Convert search to lower, if search is in title or in description, return the result
    if search:
        search_lower = search.lower()
        result = [t for t in result if search_lower in t["title"].lower()
                  or (t["description"] and search_lower in t["description"].lower())]

    # Apply limit
    return result[skip:skip + limit]


@router.get("/{task_id}", response_model=Task)
def get_task_id(task_id: int):
    """Retrieve task with ID"""

    for task in db.tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks", status_code=201, response_model=Task)
def create_task(task_data: TaskCreate):
    """Create a new task"""
    global task_id_counter
    db.task_id_counter += 1

    task = {
        "id": db.task_id_counter,
        "title": task_data.title,
        "description": task_data.description,
        "completed": False
    }
    db.tasks.append(task)
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, task_data: TaskUpdate):
    """Update task completion"""

    for task in db.tasks:
        if task["id"] == task_id:
            # Only update fields that were provided
            if task_data.title is not None:
                task["title"] = task_data.title
            if task_data.description is not None:
                task["description"] = task_data.description
            if task_data.completed is not None:
                task["completed"] = task_data.completed
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@router.delete("/tasks/{task_id}")
def delete_task_id(task_id: int):
    """Delete task with ID"""

    for i, task in enumerate(db.tasks):
        if task["id"] == task_id:
            db.tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail="Task not found")
