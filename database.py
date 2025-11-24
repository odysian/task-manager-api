from fastapi import HTTPException
from typing import Dict, Any
from datetime import datetime, timedelta, date

# In-memory storage (will be replaced with database later)
tasks = []
task_id_counter = 0

# Sample data for testing

now = datetime.now()
today = date.today()

sample_tasks = [
    {"id": 1, "title": "Learn FastAPI", "description": "Complete the tutorial", "completed": False, "priority": "high", "created_at": now - timedelta(days=7), "due_date": today + timedelta(days=2), "tags": ["learning", "backend"]},
    {"id": 2, "title": "Build Task API", "description": "Create CRUD endpoints", "completed": True, "priority": "medium", "created_at": now - timedelta(days=6), "due_date": None, "tags": ["backend", "api"]},
    {"id": 3, "title": "Add authentication", "description": None, "completed": False, "priority": "low", "created_at": now - timedelta(days=5), "due_date": today - timedelta(days=1), "tags": ["security", "backend"]},
    {"id": 4, "title": "Deploy to AWS", "description": "Use ECS for deployment", "completed": False, "priority": "high", "created_at": now - timedelta(days=4), "due_date": today, "tags": ["devops", "aws"]},
    {"id": 5, "title": "Write tests", "description": "Add pytest test suite", "completed": False, "priority": "medium", "created_at": now - timedelta(days=3), "due_date": today + timedelta(days=7), "tags": ["testing", "backend"]},
    {"id": 6, "title": "Setup CI/CD", "description": "GitHub Actions pipeline", "completed": True, "priority": "low", "created_at": now - timedelta(days=2), "due_date": None, "tags": ["devops", "automation"]},
    {"id": 7, "title": "Add pagination", "description": "Implement skip and limit", "completed": False, "priority": "medium", "created_at": now - timedelta(days=1), "due_date": today + timedelta(days=3), "tags": ["backend", "api"]},
    {"id": 8, "title": "Document API", "description": None, "completed": True, "priority": "high", "created_at": now, "due_date": None, "tags": ["documentation"]},
]
tasks.extend(sample_tasks)
task_id_counter = len(tasks)

def get_task_by_id(task_id: int) -> dict:  # type: ignore
    """
    Find a task by ID or raise 404.
    This centralizes the search logic so endpoints dont repeat it.
    """
    for task in tasks:
        if task["id"] == task_id:
            return task
    
    # Raise AFTER the loop finishes - not inside it
    raise HTTPException(
        status_code=404,
        detail=f"Task with id {task_id} not found"
    )
