import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

import db_models
from core.email import email_service

logger = logging.getLogger(__name__)


class NotificationType:
    """Enum for notification event types"""

    TASK_SHARED = "task_shared"
    TASK_COMPLETED = "task_completed"
    COMMENT_ADDED = "comment_added"
    TASK_DUE_SOON = "task_due_soon"


def send_direct_email(
    recipient_email: str, subject: str, body_text: str, body_html: str = None  # type: ignore
) -> bool:
    """
    Send email directly via email service (Resend or AWS SES).
    Used for emails like verifications, password reset.

    Returns True if successful.
    """
    return email_service.send_email(
        recipient_email=recipient_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


def get_or_create_preferences(
    user_id: int, db_session: Session
) -> db_models.NotificationPreference:
    """
    Get user's notification preferences
    Creates default preferences if they don't exist
    """
    prefs = (
        db_session.query(db_models.NotificationPreference)
        .filter(db_models.NotificationPreference.user_id == user_id)
        .first()
    )

    if not prefs:
        logger.info(f"Creating default notification preferences for user_id={user_id}")
        prefs = db_models.NotificationPreference(user_id=user_id)
        db_session.add(prefs)
        db_session.commit()
        db_session.refresh(prefs)

    return prefs


def should_notify(user_id: int, notification_type: str, db_session: Session) -> bool:
    """
    Check if user wants this type of notification
    Returns False if:
    - User has notifications disabled
    - User hasn't verified email
    - User disabled this specific notification type
    """
    prefs = get_or_create_preferences(user_id, db_session)

    # 1. Check if email is verified
    if not prefs.email_verified:  # type: ignore
        logger.debug(f"Skipping notification: user_id={user_id} email not verified")
        return False

    # 2. Check if notifications are globally disabled
    if not prefs.email_enabled:  # type: ignore
        logger.debug(f"Skipping notification: user_id={user_id} has disabled email")
        return False

    # 3. Check specific notification type
    type_mapping = {
        NotificationType.TASK_SHARED: prefs.task_shared_with_me,
        NotificationType.TASK_COMPLETED: prefs.task_completed,
        NotificationType.COMMENT_ADDED: prefs.comment_on_my_task,
        NotificationType.TASK_DUE_SOON: prefs.task_due_soon,
    }

    enabled = type_mapping.get(notification_type, False)
    if not enabled:  # type: ignore
        logger.debug(
            f"Skipping notification: user_id={user_id} disabled {notification_type}"
        )
        return False

    return True


def send_notification(
    recipient_email: str, subject: str, message: str, notification_type: str
) -> bool:
    """
    Send notification via email service (Resend or AWS SES).
    Returns True if successful, False otherwise.

    Note: With Resend, we send directly. With AWS, this could use SNS if configured,
    but for simplicity we use direct email for both.
    """
    logger.info(
        f"Sending notification: type={notification_type}, recipient={recipient_email}"
    )

    # Send as plain text email (can be enhanced with HTML templates later)
    return email_service.send_email(
        recipient_email=recipient_email,
        subject=subject,
        body_text=message,
        body_html=None,  # Can add HTML templates later
    )


def subscribe_user_to_notifications(user_email: str) -> Optional[str]:
    """
    Subscribe a user's email to notifications.

    With Resend: No subscription needed - emails are sent directly.
    With AWS SNS: Would subscribe to topic (not implemented for simplicity).

    Returns a subscription identifier if applicable, None otherwise.
    """
    # With Resend, no subscription is needed - emails are sent directly
    # This function is kept for API compatibility but doesn't do anything
    logger.info(
        f"User {user_email} is ready to receive notifications (no subscription needed with current email provider)"
    )
    return "subscribed"  # Return a dummy value for compatibility


# --- Message Templates ---


def format_task_shared_notification(
    task_title: str, sharer_username: str, permission: str
) -> tuple[str, str]:
    """Returns (subject, message) for task shared notification"""
    subject = f"Task Shared: {task_title}"
    message = f"""
Hello!

{sharer_username} has shared a task with you:

Task: {task_title}
Permission: {permission}

Log in to see the task: http://localhost:8000/tasks

---
Task Manager Notifications
    """.strip()

    return subject, message


def format_task_completed_notification(
    task_title: str, completer_username: str
) -> tuple[str, str]:
    """Returns (subject, message) for task completed notification"""
    subject = f"Task Completed: {task_title}"
    message = f"""
Hello!

{completer_username} has marked a task as completed:

Task: {task_title}

Log in to see details: http://localhost:8000/tasks

---
Task Manager Notifications
    """.strip()

    return subject, message


def format_comment_added_notification(
    task_title: str, commenter_username: str, comment_preview: str
) -> tuple[str, str]:
    """Returns (subject, message) for new comment notification"""
    subject = f"New Comment: {task_title}"

    # Truncate comment preview if it's too long
    if len(comment_preview) > 100:
        comment_preview = comment_preview[:97] + "..."

    message = f"""
Hello!

{commenter_username} commented on a task:

Task: {task_title}
Comment: "{comment_preview}"

Log in to see the discussion: http://localhost:8000/tasks

---
Task Manager Notifications
    """.strip()

    return subject, message
