import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

import db_models

logger = logging.getLogger(__name__)

# AWS SNS Config
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

sns_client = boto3.client(
    "sns",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

ses_client = boto3.client(
    "ses",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


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
    Send email directly via SES
    User for emails like verifications, password reset.

    Returns True if successful.
    """

    sender_email = "faros@odysian.dev"

    try:
        # Build email
        message = {"Subject": {"Data": subject}, "Body": {}}

        if body_text:
            message["Body"]["Text"] = {"Data": body_text}

        if body_html:
            message["Body"]["Html"] = {"Data": body_html}

        response = ses_client.send_email(
            Source=sender_email,
            Destination={"ToAddresses": [recipient_email]},
            Message=message,
        )

        logger.info(
            f"Direct email sent to {recipient_email}, "
            f"MessageId: {response['MessageId']}"
        )
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code == "MessageRejected":
            logger.error(f"Email rejected: {recipient_email} - {e}")
        elif error_code == "MailFromDomainNotVerified":
            logger.error(f"Sender domain not verified in SES: {sender_email}")
        else:
            logger.error(f"Failed to send email: {e}")

        return False


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
    Send notification via SNS.
    Returns True if successful, False otherwise.
    """
    if not SNS_TOPIC_ARN:
        logger.error("SNS_TOPIC_ARN not configured")
        return False

    try:
        # Publish to the topic with Message Attributes
        # This allows us to filter who receives it using Subscription Filter Policies
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message,
            MessageAttributes={
                "notification_type": {
                    "DataType": "String",
                    "StringValue": notification_type,
                },
                "recipient": {"DataType": "String", "StringValue": recipient_email},
            },
        )

        logger.info(
            f"Notification sent: type={notification_type}, "
            f"recipient={recipient_email}, message_id={response['MessageId']}"
        )
        return True

    except ClientError as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def subscribe_user_to_notifications(user_email: str) -> Optional[str]:
    """
    Subscribe a user's email to the SNS topic.
    AWS will send a confirmation email.
    """
    if not SNS_TOPIC_ARN:
        logger.error("SNS_TOPIC_ARN not configured")
        return None

    try:
        # In production, we would add a filter policy here
        # so users ONLY get messages where recipient == their email.
        # For now, we subscribe generically.
        response = sns_client.subscribe(
            TopicArn=SNS_TOPIC_ARN,
            Protocol="email",
            Endpoint=user_email,
            ReturnSubscriptionArn=True,
        )

        subscription_arn = response.get("SubscriptionArn")
        logger.info(f"Subscribed {user_email} to notifications: {subscription_arn}")
        return subscription_arn

    except ClientError as e:
        logger.error(f"Failed to subscribe {user_email}: {e}")
        return None


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
