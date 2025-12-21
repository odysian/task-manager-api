from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import db_models
from core.exceptions import UnauthorizedTaskAccessError
from core.security import verify_access_token
from db_config import get_db


# Custom HTTPBearer that raises 401 instead of 403
class HTTPBearerAuth(HTTPBearer):
    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        try:
            return await super().__call__(request)
        except HTTPException:
            # Override the default 403 with 401
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )


class TaskPermission(Enum):
    NONE = "none"
    VIEW = "view"
    EDIT = "edit"
    OWNER = "owner"


# This tells FastAPI to look for "Authorization: Bearer <token>" header
security = HTTPBearerAuth()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_session: Session = Depends(get_db),
) -> db_models.User:
    """
    Dependency that extracts and verifies JWT token from request
    Returns the authenticated User object.
    Raises 401 if token is missing, invalid, or user not found.
    Also stores user in request.state for rate limiting.
    """
    # Extract token from credentials
    token = credentials.credentials

    # Verify and decode token
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract username from token payload
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up user in database
    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.username == username)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.user = user

    return user


def get_user_task_permission(
    task: db_models.Task, user: db_models.User, db_session: Session
) -> TaskPermission:
    """
    Determine what permission a user has on a task.

    Returns:
        OWNER - User owns the task
        EDIT - Task is shared with user with edit permission
        VIEW - Task is shared with user with view permission
        NONE - User has no access
    """
    # Owner has full access
    if task.user_id == user.id:  # type: ignore
        return TaskPermission.OWNER

    # Check if task is shared with this user
    share = (
        db_session.query(db_models.TaskShare)
        .filter(
            db_models.TaskShare.task_id == task.id,
            db_models.TaskShare.shared_with_user_id == user.id,
        )
        .first()
    )

    if not share:
        return TaskPermission.NONE

    if share.permission == "edit":  # type: ignore
        return TaskPermission.EDIT
    else:
        return TaskPermission.VIEW


def require_task_access(
    task: db_models.Task,
    user: db_models.User,
    db_session: Session,
    min_permission: TaskPermission = TaskPermission.VIEW,
):
    """
    Raise exception if user doesn't have required permission.

    Usage:
        require_task_access(task, current_user, db_session, TaskPermission.EDIT)
    """
    user_permission = get_user_task_permission(task, user, db_session)

    # Define permission hierarchy
    permission_levels = {
        TaskPermission.NONE: 0,
        TaskPermission.VIEW: 1,
        TaskPermission.EDIT: 2,
        TaskPermission.OWNER: 3,
    }

    if permission_levels[user_permission] < permission_levels[min_permission]:
        raise UnauthorizedTaskAccessError(
            task_id=task.id,  # type: ignore
            user_id=user.id,  # type: ignore
        )
