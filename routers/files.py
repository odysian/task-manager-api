import logging
import os
import uuid
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session
from db_config import get_db
from dependencies import get_current_user
import db_models
from models import FileUploadResponse, TaskFileInfo
import exceptions
from rate_limit_config import limiter
from dependencies import require_task_access, TaskPermission

# AWS S3 Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Create S3 Client
s3_client = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Router for task-related file endpoints
task_files_router = APIRouter(prefix="/tasks", tags=["files"])

# Router for direct file operations
files_router = APIRouter(prefix="/files", tags=["files"])

# File size limit (10 MB)
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 10485760))

# Allowed file types
ALLOWED_EXTENSIONS_STR = os.getenv("ALLOWED_EXTENSIONS", ".jpg,.jpeg,.png,.gif,.pdf,.txt,.doc,.docx")
ALLOWED_EXTENSIONS = set(ext.strip() for ext in ALLOWED_EXTENSIONS_STR.split(','))

logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@task_files_router.post("/{task_id}/files", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour") # 20 file uploads per hour
async def upload_file(
    request: Request,
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

    # Check if task exists and verify access permissions
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        logger.warning(f"Upload failed: task_id={task_id} not found")
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    require_task_access(task, current_user, db_session, TaskPermission.EDIT)
    
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


    # Generate unique S3 key
    unique_id = str(uuid.uuid4())
    stored_filename = f"task_{task_id}_{unique_id}{file_ext}"
    
    # Upload to S3
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=stored_filename,
            Body=content,
            ContentType=file.content_type or 'application/octet-stream'
        )
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage"
        )

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

@task_files_router.get("/{task_id}/files", response_model=list[TaskFileInfo])
def list_task_files(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """List all files attached to a task"""
    logger.info(f"Listing files for task_id={task_id}, user_id={current_user.id}")

    # Check if task exists and verify access permissions
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    require_task_access(task, current_user, db_session, TaskPermission.VIEW)
    
    # Use the relationship
    files = task.files

    logger.info(f"Found {len(files)} files for task_id={task_id}")

    return files

@files_router.get("/{file_id}")
async def download_file(
    file_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """
    Download a file by its ID.
    Returns the actual file for download
    """
    logger.info(f"File download request: file_id={file_id}, user_id={current_user.id}")

    # Get the file record
    task_file = db_session.query(db_models.TaskFile).filter(
        db_models.TaskFile.id == file_id
    ).first()

    if not task_file:
        logger.warning(f"Download failed: file_id={file_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID {file_id} not found"
        )
    # Verify user has permission to access the parent task
    require_task_access(task_file.task, current_user, db_session, TaskPermission.VIEW)
    
    # Download file from S3
    try:
        s3_response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=task_file.stored_filename
        )
        file_content = s3_response['Body'].read()

        logger.info(f"File download successful: file_id={file_id}, filename={task_file.original_filename}")

        # Wrap in BytesIO and stream to user
        file_stream = BytesIO(file_content)

        return StreamingResponse(
            file_stream,
            media_type=task_file.content_type or 'application/octet-stream', # type: ignore
            headers={
                "Content-Disposition": f"attachment; filename='{task_file.original_filename}'"
            }
        )
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.error(f"Download failed: file not found in S3: {task_file.stored_filename}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage"
            )
        else:
            logger.error(f"S3 download failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download file from storage"
            )

@files_router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Delete a file by its ID"""
    logger.info(f"File delete request: file_id={file_id}, user_id={current_user.id}")

    #Get the file record
    task_file = db_session.query(db_models.TaskFile).filter(
        db_models.TaskFile.id == file_id
    ).first()

    if not task_file:
        logger.warning(f"Download failed: file_id={file_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID {file_id} not found"
        )
    
    # Verify user has permission to access the parent task
    require_task_access(task_file.task, current_user, db_session, TaskPermission.EDIT)
    
    # Save filename before deleting from DB
    stored_filename: str = task_file.stored_filename # type: ignore
    original_filename: str = task_file.original_filename # type: ignore

    # Delete from database
    db_session.delete(task_file)
    db_session.commit()

    # Delete from S3
    try:
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=stored_filename
        )
        logger.info(f"Deleted file from S3: {stored_filename}")
    except ClientError as e:
        # Log warning but don't fail - file might already be gone
        logger.warning(f"S3 deletion warning for {stored_filename}: {e}")

    logger.info(f"File deleted successfully: file_id={file_id}, filename={original_filename}")

    return None





