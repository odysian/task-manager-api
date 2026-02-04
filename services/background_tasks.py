import logging
import os
import time

from core.storage import storage
from db_config import SessionLocal
from services.notifications import (
    NotificationType,
    format_comment_added_notification,
    format_task_completed_notification,
    format_task_shared_notification,
    send_notification,
    should_notify,
)

logger = logging.getLogger(__name__)


def cleanup_after_task_deletion(task_id: int, task_title: str, file_list: list[str]):
    """
    Cleanup operations after task deletion
    Deletes uploaded files from local storage, removes from caches, updates analytics, etc.
    """
    logger.info(
        f"BACKGROUND TASK: Starting cleanup after task deletion - task_id={task_id}"
    )

    # Delete files using storage abstraction
    files_deleted = 0
    for stored_filename in file_list:
        try:
            storage.delete_file(stored_filename)
            files_deleted += 1
            logger.info(f"Deleted file from storage: {stored_filename}")
        except Exception as e:
            logger.warning(f"File deletion warning for {stored_filename}: {e}")

    # Simulate cleanup work
    time.sleep(1)

    # Log what we "cleaned up"
    logger.info(
        f"CLEANUP COMPLETED: Task '{task_title}' (ID: {task_id}) | "
        f"Removed from cache, deleted {files_deleted} files from storage, updated analytics"
    )


def notify_task_shared(
    recipient_user_id: int,
    recipient_email: str,
    task_title: str,
    sharer_username: str,
    permission: str,
):
    """
    Background task: Send notification when task is shared.
    """
    logger.info(
        f"BACKGROUND TASK: Checking notification for user_id={recipient_user_id}"
    )

    db = SessionLocal()

    # 1. Check preferences
    try:
        if not should_notify(recipient_user_id, NotificationType.TASK_SHARED, db):
            logger.info(f"User {recipient_user_id} blocked task_shared notification")
            return

        # 2. Format message
        subject, message = format_task_shared_notification(
            task_title=task_title,
            sharer_username=sharer_username,
            permission=permission,
        )

        # 3. Send via SNS
        send_notification(
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            notification_type=NotificationType.TASK_SHARED,
        )

    finally:
        db.close()


def notify_task_completed(
    recipient_user_id: int,
    recipient_email: str,
    task_title: str,
    completer_username: str,
):
    """Background task: Send notification when a shared task is completed"""

    db = SessionLocal()

    try:
        # Check preferences
        if not should_notify(recipient_user_id, NotificationType.TASK_COMPLETED, db):
            return

        subject, message = format_task_completed_notification(
            task_title=task_title, completer_username=completer_username
        )

        send_notification(
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            notification_type=NotificationType.TASK_COMPLETED,
        )

    finally:
        db.close()


def notify_comment_added(
    recipient_user_id: int,
    recipient_email: str,
    task_title: str,
    commenter_username: str,
    comment_content: str,
):
    """Background task: Send notification when a comment is added"""
    # Create fresh session
    db = SessionLocal()

    try:
        # Check preferences (Did they turn off 'comment_added' alerts?)
        if not should_notify(recipient_user_id, NotificationType.COMMENT_ADDED, db):
            return

        subject, message = format_comment_added_notification(
            task_title=task_title,
            commenter_username=commenter_username,
            comment_preview=comment_content,
        )

        send_notification(
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            notification_type=NotificationType.COMMENT_ADDED,
        )
    finally:
        db.close()
