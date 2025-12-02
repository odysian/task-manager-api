import os
from dotenv import load_dotenv

# Load environment varaibles first
load_dotenv()

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

import exceptions
from logging_config import setup_logging
from routers import tasks, auth, files, health

# cd task-manager-api
# source venv/bin/activate
# uvicorn main:app --reload
# Open:  http://localhost:8000/docs
# Ctrl+C to stop the server
# deactivate  # optional, closing terminal does this anyway

# Initialize logging FIRST
setup_logging()

# Get logger for this module
logger = logging.getLogger(__name__)

# Check if testing before importing rate limiter
TESTING = os.getenv("TESTING", "false").lower() == "true"

if not TESTING:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from rate_limit_config import limiter

# --- Application Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Task Manager API starting up")
    yield
    # Shutdown
    logger.info("Task Manager API shutting down")

app = FastAPI(
    title="Task Manager API",
    description="A simple task management API",
    version="0.1.0",
    lifespan=lifespan
)

# Only add rate limiter if not testing
if not TESTING:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
    logger.info("Rate limiting enabled")
else:
    logger.info("Rate limiting disabled (testing mode)")


# Log application startup
logger.info("Task Manager API starting up")

@app.get("/")
def root():
    """Health check / welcome endpoint"""
    return {"message": "Task Manager API", "status": "running"}

app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(files.task_files_router)
app.include_router(files.files_router)
app.include_router(health.router)


# --- Exception Handlers ---

@app.exception_handler(exceptions.TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: exceptions.TaskNotFoundError):
    """Handle TaskNotFoundError by returning 404"""
    logger.error(f"TaskNotFoundError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Task Not Found",
            "message": exc.message,
            "task_id": exc.task_id
        }
    )

@app.exception_handler(exceptions.UnauthorizedTaskAccessError)
async def unauthorized_task_handler(request: Request, exc: exceptions.UnauthorizedTaskAccessError):
    """Handle UnauthorizedTaskAccessError by returning 403"""
    logger.warning(f"UnauthorizedTaskAccessError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "Unauthorized Access",
            "message": "You do not have permission to access this task"
            # Don't expose task_id or user_id in response for security
        }
    )

@app.exception_handler(exceptions.TagNotFoundError)
async def tag_not_found_handler(request: Request, exc: exceptions.TagNotFoundError):
    """Handle TagNotFoundError by returning 404"""
    logger.error(f"TagNotFoundError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Tag Not Found",
            "message": exc.message,
            "task_id": exc.task_id,
            "tag": exc.tag
        }
    )

@app.exception_handler(exceptions.DuplicateUserError)
async def duplicate_user_handler(request: Request, exc: exceptions.DuplicateUserError):
    """Handle DuplicateUserError by returning 409"""
    logger.warning(f"DuplicateUserError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "Duplicate User",
            "message": exc.message,
            "field": exc.field
        }
    )

@app.exception_handler(exceptions.InvalidCredentialsError)
async def invalid_credentials_handler(request: Request, exc: exceptions.InvalidCredentialsError):
    """Handle InvalidCredentialsError by returning 401"""
    logger.warning(f"InvalidCredentialsError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": "Authentication Failed",
            "message": exc.message
        },
        headers={"WWW-Authenticate": "Bearer"}
    )

