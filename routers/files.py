import logging
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from db_config import get_db
from dependencies import get_current_user
import db_models
from models import FileUploadResponse, TaskFileInfo
import exceptions

router = APIRouter(prefix="/tasks", tags=["files"])
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# File size limit (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed file types
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".pdf", 
    ".doc", ".docx", ".txt", ".zip"
}

@router.post("/{task_id}/files", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    task_id: int,
    file: UploadFile = File(...),
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """
    Upload a file and attach it to a task.
    - Max file size: 10 MB
    - Allowed types: images, PDFs, documents
    """
    logger.info(f"File upload attempt for task_id={task_id} by user_id={current_user.id}: filename={file.filename}")

    # Check if task exists and user owns it
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        logger.warning(f"Upload failed: task_id={task_id} not found")
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    if task.user_id != current_user.id:  # type: ignore
        logger.warning(f"Upload failed: user_id={current_user.id} tried to upload to task_id={task_id}")
        raise exceptions.UnauthorizedTaskAccessError(task_id=task_id, user_id=current_user.id)  # type: ignore
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower() # type: ignore
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Upload failed: invalid file type {file_ext}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size > MAX_FILE_SIZE:
        logger.warning(f"Upload failed: file too large ({file_size} bytes)")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024} MB"
        )


    # Generate unique filename
    unique_id = str(uuid.uuid4())
    stored_filename = f"task_{task_id}_{unique_id}{file_ext}"
    file_path = UPLOAD_DIR / stored_filename
    
    # Save file to disk
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"File saved to disk: {stored_filename} ({file_size} bytes)")

    # Create database record
    task_file = db_models.TaskFile(
        task_id=task_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_size=file_size,
        content_type=file.content_type
    )

    db_session.add(task_file)
    db_session.commit()
    db_session.refresh(task_file)

    logger.info(f"File uploaded successfully: file_id={task_file.id}, task_id={task_id}, user_id={current_user.id}")

    return task_file

@router.get("/{task_id}/files", response_model=list[TaskFileInfo])
def list_task_files(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """List all files attached to a task"""
    logger.info(f"Listing files for task_id={task_id}, user_id={current_user.id}")

    # Check if task exists and user owns it
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    if task.user_id != current_user.id:  # type: ignore
        raise exceptions.UnauthorizedTaskAccessError(task_id=task_id, user_id=current_user.id)  # type: ignore
    
    # Use the relationship
    files = task.files

    logger.info(f"Found {len(files)} files for task_id={task_id}")

    return files
