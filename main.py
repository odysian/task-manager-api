from fastapi import FastAPI
from routers import tasks

# cd task-manager-api
# source venv/bin/activate
# uvicorn main:app --reload
# Open:  http://localhost:8000/docs
# Ctrl+C to stop the server
# deactivate  # optional, closing terminal does this anyway


# --- Application Setup ---

app = FastAPI(
    title="Task Manager API",
    description="A simple task management API",
    version="0.1.0"
)


@app.get("/")
def root():
    """Health check / welcome endpoint"""
    return {"message": "Task Manager API", "status": "running"}

app.include_router(tasks.router)
