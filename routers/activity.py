# routers/activity.py

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

import activity_service
import db_models
from db_config import get_db
from dependencies import TaskPermission, get_current_user, require_task_access
from exceptions import TaskNotFoundError
from models import ActivityLogResponse, ActivityQuery

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


@router.get("/tasks/{task_id}", response_model=list[ActivityLogResponse])
def get_task_timeline(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Get complete activity timeline for a specific task.

    Shows all actions performed on this task (create, updates, shares, etc.)
    Only return logs if user has access to the task.
    """
    # Get task
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise TaskNotFoundError(task_id=task_id)

    # Check permission
    require_task_access(task, current_user, db_session, TaskPermission.VIEW)

    # Get all activity for this task
    logs = (
        db_session.query(db_models.ActivityLog)
        .options(joinedload(db_models.ActivityLog.user))
        .filter(
            db_models.ActivityLog.resource_type == "task",
            db_models.ActivityLog.resource_id == task_id,
        )
        .order_by(db_models.ActivityLog.created_at)
        .all()
    )

    # Convert to response
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
