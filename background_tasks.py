import logging
import time
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# AWS S3 Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Create S3 client
s3_client = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def send_task_completion_notification(user_email: str, task_title: str, task_id: int):
    """
    Send notification when a task is completed.
    In production this would send an actual email.
    """

    logger.info(f"BACKGROUND TASK: Sending completion notification for task_id={task_id}")

    # Simulate email sending delay
    time.sleep(2)

    # Log the "sent notification"
    logger.info(
        f"NOTIFICATION SENT: Task '{task_title}' completed | "
        f"Recipient: {user_email} | "
        f"Task ID: {task_id} | "
        f"Time: {datetime.now()}"
    )

def cleanup_old_tasks(days_old: int):
    """
    Example of a periodic cleanup task.
    Could be triggered by an endpoint or scheduled externally.
    """
    logger.info(f"BACKGROUND TASK: Starting cleanup of tasks older than {days_old} days")
    # In production: delete old completed tasks, compress data, etc.
    time.sleep(1)
    logger.info(f"BACKGROUND TASK: Cleanup completed")

def cleanup_after_task_deletion(task_id: int, task_title: str, file_list: list[str]):
    """
    Cleanup operations after task deletion
    In Production: delete uploaded files from S3, remove from caches, update analytics, etc.
    """
    logger.info(f"BACKGROUND TASK: Starting cleanup after task deletion - task_id={task_id}")

    # Delete files from disk
    files_deleted = 0
    for stored_filename in file_list:
        try:
            s3_client.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=stored_filename
            )
            files_deleted += 1
            logger.info(f"Deleted file from S3: {stored_filename}")
        except ClientError as e:
            logger.warning(f"S3 deletion warning for {stored_filename}: {e}")

    # Simulate cleanup work
    time.sleep(1)

    # Log what we "cleaned up"
    logger.info(
        f"CLEANUP COMPLETED: Task '{task_title}' (ID: {task_id}) | "
        f"Removed from cache, deleted {files_deleted} from S3, updated analytics"
    )