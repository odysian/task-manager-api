# Week 1-2 Concepts Cheatsheet

Personal reference guide for FastAPI and Python backend concepts learned.

---

## FastAPI Basics

### Creating an App
```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="What it does",
    version="1.0.0"
)
```

### HTTP Methods (CRUD)
| Method | Purpose | Example Use |
|--------|---------|-------------|
| GET | Read/retrieve data | Get all tasks, get one task |
| POST | Create new data | Create a new task |
| PUT | Replace entire resource | Replace a whole task |
| PATCH | Update part of resource | Update just the title |
| DELETE | Remove data | Delete a task |

### Status Codes (Important Ones)
- `200 OK` - Success (GET, PATCH, PUT)
- `201 Created` - Successfully created (POST)
- `204 No Content` - Success with no response body (DELETE)
- `400 Bad Request` - Client sent invalid data
- `404 Not Found` - Resource doesn't exist
- `422 Unprocessable Entity` - Data validation failed
- `500 Internal Server Error` - Something broke on server

### Basic Route
```python
@app.get("/")
def root():
    return {"message": "Hello"}
```

---

## Pydantic Models (Data Validation)

### Why Use Them?
- Automatic validation (type checking, constraints)
- Auto-generated API documentation
- Clear data structures
- Helpful error messages

### Basic Model
```python
from pydantic import BaseModel
from typing import Optional

class Task(BaseModel):
    id: int
    title: str
    completed: bool
    description: Optional[str] = None  # Optional field
```

### Field Constraints
```python
from pydantic import Field

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
```

Common constraints:
- `min_length`, `max_length` - for strings
- `ge` (>=), `le` (<=), `gt` (>), `lt` (<) - for numbers
- `default` - default value if not provided
- `default_factory` - for mutable defaults like lists

### Literal Types (Restrict to Specific Values)
```python
from typing import Literal

priority: Literal["low", "medium", "high"]
# Only accepts these three exact values
```

### Config Options
```python
class TaskCreate(BaseModel):
    title: str
    
    class Config:
        str_strip_whitespace = True  # Remove leading/trailing spaces
```

---

## Path Parameters vs Query Parameters

### Path Parameters (Part of URL)
```python
@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    # URL: /tasks/5
    # task_id = 5
```

### Query Parameters (After the ?)
```python
@app.get("/tasks")
def get_tasks(completed: bool = None, limit: int = 100):
    # URL: /tasks?completed=true&limit=10
    # completed = True, limit = 10
```

### Query with Validation
```python
from fastapi import Query

@app.get("/tasks")
def get_tasks(
    limit: int = Query(default=100, ge=1, le=100)
):
    # Must be between 1 and 100
```

---

## Request Bodies (POST/PATCH)

### Simple Body
```python
@app.post("/tasks")
def create_task(task_data: TaskCreate):
    # FastAPI automatically validates against TaskCreate model
    # Access fields: task_data.title, task_data.description
```

### Getting Only Changed Fields
```python
@app.patch("/tasks/{id}")
def update_task(id: int, task_data: TaskUpdate):
    # Get only fields that were actually sent
    update_data = task_data.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(400, "No fields to update")
```

---

## Response Models

### Why Use Them?
- Documents what your API returns
- Validates your response (catches bugs)
- Can exclude sensitive fields

### Usage
```python
@app.get("/tasks/{id}", response_model=Task)
def get_task(id: int):
    return task  # FastAPI validates this matches Task model
```

### Returning Lists
```python
@app.get("/tasks", response_model=list[Task])
def get_all_tasks():
    return tasks  # List of task dictionaries
```

---

## Error Handling

### Raising HTTP Errors
```python
from fastapi import HTTPException

if not task:
    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )
```

### Common Pattern
```python
def get_task_by_id(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(404, f"Task {task_id} not found")
```

---

## Working with Dates

### Imports
```python
from datetime import datetime, date, timedelta
```

### Common Operations
```python
# Current datetime with time
now = datetime.now()  # 2025-11-23 14:30:00

# Current date only
today = date.today()  # 2025-11-23

# Date math
yesterday = today - timedelta(days=1)
next_week = today + timedelta(days=7)

# Extract date from datetime
now.date()  # Returns just the date part

# Compare dates
if task_date < today:
    print("Overdue!")
```

### Date in Pydantic
```python
class Task(BaseModel):
    created_at: datetime  # Full timestamp
    due_date: Optional[date] = None  # Just the date
```

FastAPI automatically converts:
- `"2025-11-23"` → `date(2025, 11, 23)`
- `"2025-11-23T14:30:00"` → `datetime(2025, 11, 23, 14, 30, 0)`

---

## Python Patterns I've Used

### List Comprehensions
```python
# Basic filter
completed = [t for t in tasks if t["completed"]]

# With multiple conditions
overdue = [t for t in tasks 
           if t["due_date"] 
           and not t["completed"] 
           and t["due_date"] < today]

# Same as:
overdue = []
for t in tasks:
    if t["due_date"] and not t["completed"] and t["due_date"] < today:
        overdue.append(t)
```

### Lambda Functions (Anonymous Functions)
```python
# Used with sorted()
sorted(tasks, key=lambda t: t["title"])
# "For each task t, use t['title'] for sorting"

# With conditional
sorted(tasks, key=lambda t: t["due_date"] if t["due_date"] else date.max)
# "Use due_date if exists, otherwise use max date"
```

### Sorting
```python
# Sort by field
result = sorted(tasks, key=lambda t: t["priority"])

# Reverse (descending)
result = result[::-1]
# or
result = sorted(tasks, key=lambda t: t["priority"], reverse=True)
```

### List Slicing (Pagination)
```python
tasks[0:10]    # First 10 items
tasks[10:20]   # Items 10-19
tasks[skip:skip + limit]  # Pagination

# Reverse a list
tasks[::-1]
```

### Counting Patterns
```python
# Count items matching condition
count = sum(1 for t in tasks if t["completed"])

# Same as:
count = 0
for t in tasks:
    if t["completed"]:
        count += 1
```

### Counter (for aggregations)
```python
from collections import Counter

priorities = [t["priority"] for t in tasks]
counts = Counter(priorities)
# Counter({'high': 3, 'medium': 2, 'low': 1})

dict(counts)  # Convert to regular dict
# {'high': 3, 'medium': 2, 'low': 1}
```

### Dictionary Operations
```python
# Update dict
task = {"id": 1, "title": "Old"}
task.update({"title": "New", "completed": True})
# task is now {"id": 1, "title": "New", "completed": True}

# Check if key exists
if "due_date" in task:
    print(task["due_date"])

# Safe get with default
task.get("due_date", None)  # Returns None if key doesn't exist

# List extend
all_tags = []
all_tags.extend(["a", "b"])  # all_tags = ["a", "b"]
all_tags.extend(["c"])       # all_tags = ["a", "b", "c"]
```

---

## Project Structure

### Why Separate Files?
- **Modularity** - each file has one job
- **Readability** - easier to find things
- **Scalability** - can add features without cluttering one file
- **Reusability** - import models/helpers where needed

### My Structure
```
task-manager-api/
├── main.py           # App setup, include routers
├── models.py         # Pydantic schemas (data shapes)
├── database.py       # Data storage + helper functions
└── routers/
    └── tasks.py      # All task endpoints
```

### How They Connect
```python
# main.py - assembles everything
from fastapi import FastAPI
from routers import tasks

app = FastAPI()
app.include_router(tasks.router)

# routers/tasks.py - defines endpoints
from fastapi import APIRouter
import database as db
from models import Task, TaskCreate

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("", response_model=list[Task])
def get_tasks():
    return db.tasks

# models.py - defines data structures
from pydantic import BaseModel

class Task(BaseModel):
    id: int
    title: str

# database.py - stores data
tasks = []

def get_task_by_id(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(404, "Not found")
```

---

## Router Concepts

### APIRouter vs FastAPI App
- `FastAPI()` - the main application
- `APIRouter()` - a module of related endpoints
- Routers get "mounted" onto the app

### Creating a Router
```python
from fastapi import APIRouter

router = APIRouter(
    prefix="/tasks",      # All routes start with /tasks
    tags=["tasks"]        # Groups in /docs
)

@router.get("")           # Becomes /tasks
@router.get("/{id}")      # Becomes /tasks/{id}
```

### Route Order Matters!
```python
# CORRECT ORDER
@router.get("/stats")      # Specific routes first
@router.get("/{task_id}")  # Generic routes last

# WRONG ORDER
@router.get("/{task_id}")  # Would match "stats" as a task_id
@router.get("/stats")      # Never reached!
```

**Rule:** Most specific → least specific

---

## Common Mistakes I Made

### 1. Indentation in Loops
```python
# WRONG - raises error immediately
for task in tasks:
    if task["id"] == task_id:
        return task
    raise HTTPException(404, "Not found")  # In loop!

# CORRECT - raises after loop finishes
for task in tasks:
    if task["id"] == task_id:
        return task
raise HTTPException(404, "Not found")  # Outside loop
```

### 2. Tabs vs Spaces
- Python standard: 4 spaces per indent
- Never mix tabs and spaces
- VS Code setting: "Insert Spaces" = True, Tab Size = 4

### 3. Optional Type Annotations
```python
# WRONG - None is not valid for Literal type
completed: Optional[Literal[bool]] = None

# CORRECT
completed: Optional[bool] = None
```

### 4. Field() vs Query()
```python
# In Pydantic models
class Task(BaseModel):
    title: str = Field(min_length=1)  # Use Field()

# In route parameters
@app.get("/tasks")
def get_tasks(limit: int = Query(ge=1, le=100)):  # Use Query()
```

### 5. Mutable Defaults
```python
# WRONG - all instances share same list!
class Task(BaseModel):
    tags: list[str] = []

# CORRECT
class Task(BaseModel):
    tags: list[str] = Field(default_factory=list)
```

---

## Key Concepts Summary

### REST Principles
- Resources have URLs (`/tasks`, `/tasks/5`)
- HTTP methods indicate operation (GET=read, POST=create)
- Status codes indicate result
- Stateless (each request is independent)

### Validation Flow
1. Request comes in
2. FastAPI checks path parameters
3. FastAPI checks query parameters  
4. FastAPI validates request body against Pydantic model
5. If valid → your function runs
6. FastAPI validates response against response_model
7. Returns JSON to client

### When to Use What
- **Path params** - identifying a specific resource (`/tasks/5`)
- **Query params** - filtering/pagination (`?completed=true&limit=10`)
- **Request body** - sending complex data (POST/PATCH)
- **Headers** - metadata, auth tokens (not used yet)

---

## Commands I Use Daily
```bash
# Activate virtual environment
source venv/bin/activate

# Run development server
uvicorn main:app --reload

# Git workflow
git add .
git commit -m "Description of changes"
git status
git log --oneline

# Check Python version
python --version
```

---

## Next Steps (Week 3-4)

- Install PostgreSQL
- Learn SQL (SELECT, INSERT, UPDATE, DELETE, WHERE, JOIN)
- SQLAlchemy ORM (object-relational mapping)
- Database migrations with Alembic
- Replace `database.py` with real database connections

---

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Real Python](https://realpython.com/)
- [Python typing module](https://docs.python.org/3/library/typing.html)

---

**Last Updated:** November 24, 2025  
**Current Week:** 1-2 (FastAPI Fundamentals)