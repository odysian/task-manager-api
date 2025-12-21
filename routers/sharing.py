from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

import db_models
from core import exceptions
from core.redis_config import invalidate_user_cache
from db_config import get_db
from dependencies import TaskPermission, get_current_user, require_task_access
from schemas.sharing import (
    SharedTaskResponse,
    TaskShareCreate,
    TaskShareResponse,
    TaskShareUpdate,
)
from services import activity_service
from services.background_tasks import notify_task_shared

sharing_router = APIRouter(prefix="/tasks", tags=["sharing"])


@sharing_router.get("/shared-with-me", response_model=list[SharedTaskResponse])
def get_shared_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Get all tasks that have been shared with the current user"""

    # Query for shares where current user is the recipient
    shares = (
        db_session.query(db_models.TaskShare)
        .options(joinedload(db_models.TaskShare.task).joinedload(db_models.Task.owner))
        .filter(db_models.TaskShare.shared_with_user_id == current_user.id)
        .all()
    )

    return [
        {
            "task": share.task,
            "permission": share.permission,
            "is_owner": False,
            "owner_username": share.task.owner.username,
        }
        for share in shares
    ]


@sharing_router.get("/{task_id}/shares", response_model=list[TaskShareResponse])
def get_task_shares(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Get a list of users this task is shared with (owner only)"""

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.OWNER)

    shares = (
        db_session.query(db_models.TaskShare)
        .options(joinedload(db_models.TaskShare.shared_with))
        .filter(db_models.TaskShare.task_id == task_id)
        .all()
    )

    return [
        {
            "id": share.id,
            "task_id": share.task_id,
            "shared_with_user_id": share.shared_with_user_id,
            "shared_with_username": share.shared_with.username,
            "permission": share.permission,
            "shared_at": share.shared_at,
        }
        for share in shares
    ]


@sharing_router.post(
    "/{task_id}/share",
    response_model=TaskShareResponse,
    status_code=status.HTTP_201_CREATED,
)
def share_task(
    task_id: int,
    share_data: TaskShareCreate,
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Share a task with another user"""

    # Get the task
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)

    # Only owner can share
    require_task_access(task, current_user, db_session, TaskPermission.OWNER)

    # Look up user to share with
    shared_with_user = (
        db_session.query(db_models.User)
        .filter(db_models.User.username == share_data.shared_with_username)
        .first()
    )

    if not shared_with_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{share_data.shared_with_username}' not found",
        )

    # Can't share with yourself
    if shared_with_user.id == current_user.id:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot share task with yourself",
        )

    # Check if already shared
    existing_share = (
        db_session.query(db_models.TaskShare)
        .filter(
            db_models.TaskShare.task_id == task_id,
            db_models.TaskShare.shared_with_user_id == shared_with_user.id,
        )
        .first()
    )

    if existing_share:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task already shared with this user",
        )

    # Creat the share
    share = db_models.TaskShare(
        task_id=task_id,
        shared_with_user_id=shared_with_user.id,
        shared_by_user_id=current_user.id,
        permission=share_data.permission,
    )

    db_session.add(share)

    activity_service.log_task_shared(
        db_session=db_session,
        user_id=current_user.id,  # type: ignore
        task_id=task_id,
        shared_with_user=shared_with_user,
        permission=share_data.permission,
    )

    db_session.commit()
    db_session.refresh(share)

    # Trigger the background notification
    background_tasks.add_task(
        notify_task_shared,
        recipient_user_id=shared_with_user.id,  # type: ignore
        recipient_email=shared_with_user.email,  # type: ignore
        task_title=task.title,  # type: ignore
        sharer_username=current_user.username,  # type: ignore
        permission=share_data.permission,
    )

    invalidate_user_cache(current_user.id)  # type: ignore

    return {
        "id": share.id,
        "task_id": share.task_id,
        "shared_with_user_id": share.shared_with_user_id,
        "shared_with_username": shared_with_user.username,
        "permission": share.permission,
        "shared_at": share.shared_at,
    }


@sharing_router.put("/{task_id}/share/{username}")
def update_share_permission(
    task_id: int,
    username: str,
    share_update: TaskShareUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Update permission level"""

    # Get the task
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)

    # Only owner can update share permission
    require_task_access(task, current_user, db_session, TaskPermission.OWNER)

    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.username == username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found"
        )

    # Find the share
    share = (
        db_session.query(db_models.TaskShare)
        .filter(
            db_models.TaskShare.task_id == task_id,
            db_models.TaskShare.shared_with_user_id == user.id,
        )
        .first()
    )

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task is not shared with '{username}'",
        )

    share.permission = share_update.permission  # type: ignore

    # Update the share
    db_session.commit()
    db_session.refresh(share)

    return {
        "id": share.id,
        "task_id": share.task_id,
        "shared_with_user_id": share.shared_with_user_id,
        "shared_with_username": share.shared_with.username,
        "permission": share.permission,
        "shared_at": share.shared_at,
    }


@sharing_router.delete(
    "/{task_id}/share/{username}", status_code=status.HTTP_204_NO_CONTENT
)
def unshare_task(
    task_id: int,
    username: str,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Remove a user's access to a task"""

    # Get the task
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)

    # Only owner can unshare
    require_task_access(task, current_user, db_session, TaskPermission.OWNER)

    # Find the share
    share = (
        db_session.query(db_models.TaskShare)
        .join(
            db_models.User, db_models.TaskShare.shared_with_user_id == db_models.User.id
        )
        .options(joinedload(db_models.TaskShare.shared_with))
        .filter(
            db_models.TaskShare.task_id == task_id,
            db_models.User.username == username,
        )
        .first()
    )

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task is not shared with user '{username}",
        )

    activity_service.log_task_unshared(
        db_session=db_session,
        user_id=current_user.id,  # type: ignore
        task_id=task_id,
        unshared_user=share.shared_with,
    )

    # Delete the share
    db_session.delete(share)
    db_session.commit()

    invalidate_user_cache(current_user.id)  # type: ignore
