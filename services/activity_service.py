# pyright: reportGeneralTypeIssues=false

from typing import Any, Optional, cast

from sqlalchemy.orm import Session

import db_models
from schemas.activity import ActivityLogCreate


def log_activity(
    db_session: Session,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    details: Optional[dict[str, Any]] = None,
) -> db_models.ActivityLog:
    """Core function to log any user activity."""
    log_data = ActivityLogCreate(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )

    db_log = db_models.ActivityLog(**log_data.model_dump())
    db_session.add(db_log)

    return db_log


# --- Task Activity Logging ---


def log_task_created(
    db_session: Session, user_id: int, task: db_models.Task
) -> db_models.ActivityLog:
    """Log task creation."""

    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="created",
        resource_type="task",
        resource_id=task.id,  # type: ignore
        details={
            "title": task.title,
            "priority": task.priority,
            "completed": task.completed,
            "tags": task.tags if task.tags else [],
            "due_date": task.due_date.isoformat() if task.due_date else None,
        },
    )


def log_task_updated(
    db_session: Session,
    user_id: int,
    task: db_models.Task,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
) -> db_models.ActivityLog:
    """Log task update with old and new values."""
    changed_fields = [
        field
        for field in new_values.keys()
        if old_values.get(field) != new_values.get(field)
    ]

    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="updated",
        resource_type="task",
        resource_id=task.id,  # type: ignore
        details={
            "changed_fields": changed_fields,
            "old_values": old_values,
            "new_values": new_values,
        },
    )


def log_task_deleted(
    db_session: Session, user_id: int, task: db_models.Task
) -> db_models.ActivityLog:
    """Log task deletion. Call BEFORE deleting the task!"""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="deleted",
        resource_type="task",
        resource_id=task.id,  # type: ignore
        details={
            "title": task.title,
            "priority": task.priority,
            "completed": task.completed,
            "tags": task.tags if task.tags else [],  # type: ignore
            "due_date": task.due_date.isoformat() if task.due_date else None,
        },
    )


def log_task_shared(
    db_session: Session,
    user_id: int,
    task_id: int,
    shared_with_user: db_models.User,
    permission: str,
) -> db_models.ActivityLog:
    """Log task sharing."""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="shared",
        resource_type="task",
        resource_id=task_id,
        details={
            "shared_with_user_id": shared_with_user.id,
            "shared_with_username": shared_with_user.username,
            "permission": permission,
        },
    )


def log_task_unshared(
    db_session: Session, user_id: int, task_id: int, unshared_user: db_models.User
) -> db_models.ActivityLog:
    """Log task unsharing."""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="unshared",
        resource_type="task",
        resource_id=task_id,
        details={
            "unshared_user_id": unshared_user.id,
            "unshared_username": unshared_user.username,
        },
    )


# --- Comment Activity Logging ---


def log_comment_created(
    db_session: Session, user_id: int, comment: db_models.TaskComment
) -> db_models.ActivityLog:
    """Log comment creation."""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="created",
        resource_type="comment",
        resource_id=comment.id,  # type: ignore
        details={"task_id": comment.task_id, "content_preview": comment.content[:100]},
    )


def log_comment_updated(
    db_session: Session,
    user_id: int,
    comment: db_models.TaskComment,
    old_content: str,
    new_content: str,
) -> db_models.ActivityLog:
    """Log comment update."""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="updated",
        resource_type="comment",
        resource_id=comment.id,  # type: ignore
        details={
            "task_id": comment.task_id,
            "old_content": old_content[:100],
            "new_content": new_content[:100],
        },
    )


def log_comment_deleted(
    db_session: Session, user_id: int, comment: db_models.TaskComment
) -> db_models.ActivityLog:
    """Log comment deletion. Call BEFORE deleting!"""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="deleted",
        resource_type="comment",
        resource_id=comment.id,  # type: ignore
        details={"task_id": comment.task_id, "content": comment.content[:100]},
    )


# --- File Activity Logging ---


def log_file_uploaded(
    db_session: Session, user_id: int, task_file: db_models.TaskFile
) -> db_models.ActivityLog:
    """Log file upload."""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="uploaded",
        resource_type="file",
        resource_id=task_file.id,  # type: ignore
        details={
            "task_id": task_file.task_id,
            "filename": task_file.original_filename,
            "file_size": task_file.file_size,
            "content_type": task_file.content_type,
        },
    )


def log_file_deleted(
    db_session: Session, user_id: int, task_file: db_models.TaskFile
) -> db_models.ActivityLog:
    """Log file deletion. Call BEFORE deleting!"""
    return log_activity(
        db_session=db_session,
        user_id=user_id,
        action="deleted",
        resource_type="file",
        resource_id=task_file.id,  # type: ignore
        details={"task_id": task_file.task_id, "filename": task_file.original_filename},
    )


# --- Summary Generation ---


def get_activity_summary(log: db_models.ActivityLog) -> str:  # type: ignore
    """Generate human-readable summary of an activity log."""

    # Handle username
    username = log.user.username if log.user else f"User {log.user_id}"
    resource = f"{log.resource_type} #{log.resource_id}"

    # For actions without details, return generic message
    if not log.details:
        return f"{username} {log.action} {resource}"

    # Type assertion: we know details is not None at this point
    details = cast(dict[str, Any], log.details)

    # Task actions
    if log.resource_type == "task":
        if log.action == "created":
            title = details.get("title", "")
            return f"{username} created task '{title}'"

        if log.action == "updated":
            if "changed_fields" in details:
                fields = ", ".join(details["changed_fields"])
                return f"{username} updated {fields}"
            return f"{username} updated {resource}"

        if log.action == "deleted":
            title = details.get("title", "")
            return f"{username} deleted task '{title}'"

        if log.action == "shared":
            shared_with = details.get("shared_with_username", "someone")
            permission = details.get("permission", "access")
            return f"{username} shared task with {shared_with} ({permission})"

        if log.action == "unshared":
            unshared = details.get("unshared_username", "someone")
            return f"{username} removed {unshared}'s access to task"

    # Comment actions
    if log.resource_type == "comment":
        if log.action == "created":
            return f"{username} added a comment"
        if log.action == "updated":
            return f"{username} edited a comment"
        if log.action == "deleted":
            return f"{username} deleted a comment"

    # File actions
    if log.resource_type == "file":
        if log.action == "uploaded":
            filename = details.get("filename", "a file")
            return f"{username} uploaded {filename}"
        if log.action == "deleted":
            filename = details.get("filename", "a file")
            return f"{username} deleted {filename}"

    # Fallback
    return f"{username} {log.action} {resource}"
