import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

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

def cleanup_after_task_deletion(task_id: int, task_title: str):
    """
    Cleanup operations after task deletion
    In Production: delete uploaded files, remove from caches, update analytics, etc.
    """
    logger.info(f"BACKGROUND TASK: Starting cleanup after task deletion - task_id={task_id}")

    # Simulate cleanup work
    time.sleep(1)

    # Log what we "cleaned up"
    logger.info(
        f"CLEANUP COMPLETED: Task '{task_title}' (ID: {task_id}) | "
        f"Removed from cache, deleted associated files, updated analytics"
    )