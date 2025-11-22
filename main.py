from fastapi import FastAPI, HTTPException 

# To run: uvicorn main:app --reload
# Open:  http://localhost:8000/docs

# Create the application instance
app = FastAPI(
    title="Task Manager API",
    description="A simple task management API",
    version="0.1.0"
)

# In-memory storage (will be replaced with database later)
tasks = []
task_id_counter = 0

@app.get("/")
def root():
    """Health check / welcome endpoint"""
    return {"message": "Task Manager API", "status": "running"}

@app.get("/tasks")
def get_all_tasks():
    """Retrieve all tasks"""
    return tasks

@app.get("/tasks/{task_id}")
def get_task_id(task_id: int):
    """Retrieve task with ID"""

    for task in tasks:
        if task["id"] == task_id:
            return task

    # Not found
    raise HTTPException(status_code=404, detail="Task not found")

@app.post("/tasks", status_code=201)
def create_task(title: str):
    """Create a new task"""
    global task_id_counter
    task_id_counter += 1

    task = {
        "id": task_id_counter,
        "title": title,
        "completed": False
    }

    tasks.append(task)
    return task

@app.delete("/tasks/{task_id}")
def delete_task_id(task_id: int):
    """Delete task with ID"""

    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)   # Remove by index
            return   #204 No Content - return nothing

    # Not found
    raise HTTPException(status_code=404, detail="Task not found")

@app.patch("/tasks/{task_id}")
def update_task(task_id: int, completed: bool):
    """Update task completion"""

    for task in tasks:
        if task["id"] == task_id:
            task["completed"] = completed
            return task
        
    # Not found
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
