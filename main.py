from fastapi import FastAPI, HTTPException, Query 
from pydantic import BaseModel, Field
from typing import Optional

# cd task-manager-api
# source venv/bin/activate
# uvicorn main:app --reload
# Open:  http://localhost:8000/docs
# Ctrl+C to stop the server
# deactivate  # optional, closing terminal does this anyway


# --- Pydantic Models (Schemas) ---

class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    title: str = Field(min_length=1, max_length=200) # Can't be empty
    description: Optional[str] = Field(default=None, max_length=1000)

    # Clean up leading/trailing whitespace
    class Config:
        str_strip_whitespace = True


class TaskUpdate(BaseModel):
    """Schema for updating a task"""
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


class Task(BaseModel):
    """Schema for task responses"""
    id: int
    title: str
    description: Optional[str] = None
    completed: bool


# --- Application Setup ---

# Create the application instance
app = FastAPI(
    title="Task Manager API",
    description="A simple task management API",
    version="0.1.0"
)


# In-memory storage (will be replaced with database later)
tasks = []
task_id_counter = 0


# --- Endpoints ---

@app.get("/")
def root():
    """Health check / welcome endpoint"""
    return {"message": "Task Manager API", "status": "running"}


@app.get("/tasks", response_model=list[Task])
def get_all_tasks(
    completed: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=100)
):

    """Retrieve all tasks with optional filtering"""
    result = tasks

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
    return result[:limit]


@app.get("/tasks/{task_id}", response_model=Task)
def get_task_id(task_id: int):
    """Retrieve task with ID"""

    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", status_code=201, response_model=Task)
def create_task(task_data: TaskCreate):
    """Create a new task"""
    global task_id_counter
    task_id_counter += 1

    task = {
        "id": task_id_counter,
        "title": task_data.title,
        "description": task_data.description,
        "completed": False
    }
    tasks.append(task)
    return task


@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task_data: TaskUpdate):
    """Update task completion"""

    for task in tasks:
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


@app.delete("/tasks/{task_id}")
def delete_task_id(task_id: int):
    """Delete task with ID"""

    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail="Task not found")


# Key Concepts

# 1. Path parameters vs function parameters must match:

# @app.get("/items/{item_id}")      # Path defines {item_id}
# def get_item(item_id: int):        # Function receives item_id

# 2. Finding data vs creating data:

# GET/DELETE/PATCH on /{id} = find existing item in your data structure
# POST = create new item and add to your data structure

# 3. enumerate() for deletion:
# When you need to remove an item from a list, you often need its index, not just the item itself. enumerate() gives you both:

# for index, task in enumerate(tasks):
    # index = 0, 1, 2, ...
    # task = the actual task dict
