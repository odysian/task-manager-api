# routers/activity.py

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

import db_models
from core.exceptions import TaskNotFoundError
from db_config import get_db
from dependencies import TaskPermission, get_current_user, require_task_access
from schemas.activity import ActivityLogResponse

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityLogResponse])
def get_my_activity(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
    resource_type: Optional[str] = Query(
        None, description="Filter by resource type (task, comment, file)"
    ),
    action: Optional[str] = Query(
        None,
        description="Filter by action (created, updated, deleted, shared, unshared)",
    ),
    start_date: Optional[datetime] = Query(
        None, description="Filter activities after this date"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter activities before this date"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    Get the current user's activity history with optional filtering.

    Returns activity logs ordered by most recent first
    """

    query = db_session.query(db_models.ActivityLog).filter(
        db_models.ActivityLog.user_id == current_user.id
    )

    # Filters
    if resource_type:
        query = query.filter(db_models.ActivityLog.resource_type == resource_type)

    if action:
        query = query.filter(db_models.ActivityLog.action == action)

    if start_date:
        query = query.filter(db_models.ActivityLog.created_at >= start_date)

    if end_date:
        query = query.filter(db_models.ActivityLog.created_at <= end_date)

    # Eager load user relationship to avoid N+1
    query = query.options(joinedload(db_models.ActivityLog.user))

    # Order by most recent first
    query = query.order_by(desc(db_models.ActivityLog.created_at))

    # Apply pagination
    logs = query.offset(offset).limit(limit).all()

    # Convert to response model with username
    results = []
    for log in logs:
        results.append(
            ActivityLogResponse(
                id=log.id,  # type: ignore
                user_id=log.user_id,  # type: ignore
                action=log.action,  # type: ignore
                resource_type=log.resource_type,  # type: ignore
                resource_id=log.resource_id,  # type: ignore
                details=log.details,  # type: ignore
                created_at=log.created_at,  # type: ignore
                username=log.user.username if log.user else None,
            )
        )

    return results


@router.get("/stats")
def get_activity_stats(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Get summary statistics about user's activity.

    Returns counts by action type and resource type.
    """

    # Get all user's activity
    logs = (
        db_session.query(db_models.ActivityLog)
        .filter(db_models.ActivityLog.user_id == current_user.id)
        .all()
    )

    # Count by action
    action_counts = {}
    for log in logs:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1

    # Count by resource type
    resource_counts = {}
    for log in logs:
        resource_counts[log.resource_type] = (
            resource_counts.get(log.resource_type, 0) + 1
        )

    return {
        "total_activities": len(logs),
        "by_action": action_counts,
        "by_resource": resource_counts,
    }


@router.get("/tasks/{task_id}", response_model=list[ActivityLogResponse])
def get_task_timeline(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Get complete activity timeline for a specific task"""

    # Check task exists and user has access
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.VIEW)

    # Get ALL activities that might be related
    # We'll filter in Python - simpler and more readable
    all_logs = (
        db_session.query(db_models.ActivityLog)
        .options(joinedload(db_models.ActivityLog.user))
        .order_by(db_models.ActivityLog.created_at)
        .all()
    )

    # Filter for this task in Python
    task_logs = []
    for log in all_logs:
        # Check if this activity is related to our task
        is_related = False

        # Direct task activity
        if log.resource_type == "task" and log.resource_id == task_id:  # type: ignore
            is_related = True

        # Comment/file activity (check details.task_id)
        elif log.details and log.details.get("task_id") == task_id:  # type: ignore
            is_related = True

        if is_related:
            task_logs.append(log)

    # Convert to response model
    results = []
    for log in task_logs:
        results.append(
            ActivityLogResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                created_at=log.created_at,
                username=log.user.username if log.user else None,
            )
        )

    return results
