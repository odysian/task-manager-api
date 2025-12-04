from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import TaskShareCreate, TaskShareResponse, Task, TaskShareUpdate
from db_config import get_db
from dependencies import get_current_user
import db_models
import exceptions

sharing_router = APIRouter(prefix="/tasks", tags=["sharing"])

@sharing_router.post("/{task_id}/share", response_model=TaskShareResponse, status_code=status.HTTP_201_CREATED)
def share_task(
    task_id: int,
    share_data: TaskShareCreate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Share a task with another user"""

    # Get the task
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    # Only owner can share
    if task.user_id != current_user.id: # type: ignore
        raise exceptions.UnauthorizedTaskAccessError(task_id=task_id, user_id=current_user.id) # type: ignore
    
    # Look up user to share with
    shared_with_user = db_session.query(db_models.User).filter(
        db_models.User.username == share_data.shared_with_username
    ).first()

    if not shared_with_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{share_data.shared_with_username}' not found"
        )
    
    # Can't share with yourself
    if shared_with_user.id == current_user.id: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot share task with yourself"
        )
    
    # Check if already shared
    existing_share = db_session.query(db_models.TaskShare).filter(
        db_models.TaskShare.task_id == task_id,
        db_models.TaskShare.shared_with_user_id == shared_with_user.id
    ).first()

    if existing_share:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task already shared with this user"
        )
    
    # Creat the share
    share = db_models.TaskShare(
        task_id=task_id,
        shared_with_user_id=shared_with_user.id,
        shared_by_user_id=current_user.id,
        permission=share_data.permission
    )

    db_session.add(share)
    db_session.commit()
    db_session.refresh(share)

    return {
        "id": share.id,
        "task_id": share.task_id,
        "shared_with_user_id": share.shared_with_user_id,
        "shared_with_username": shared_with_user.username,
        "permission": share.permission,
        "shared_at": share.shared_at
    }

@sharing_router.get("/shared-with-me", response_model=list[Task])
def get_shared_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Get all tasks that have been shared with the current user"""


    # Query for shares where current user is the recipient
    shares = db_session.query(db_models.TaskShare).filter(
        db_models.TaskShare.shared_with_user_id == current_user.id
    ).all()

    # Extract the tasks from shares
    tasks = [share.task for share in shares]

    return tasks

@sharing_router.delete("/{task_id}/share/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unshare_task(
    task_id: int,
    user_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Remove a user's access to a task"""

    # Get the task
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    # Only owner can unshare
    if task.user_id != current_user.id: # type: ignore
        raise exceptions.UnauthorizedTaskAccessError(task_id=task_id, user_id=current_user.id) # type: ignore
    
    # Find the share
    share = db_session.query(db_models.TaskShare).filter(
        db_models.TaskShare.task_id == task_id,
        db_models.TaskShare.shared_with_user_id == user_id
    ).first()

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task is not shared with this user"
        )
    
    # Delete the share
    db_session.delete(share)
    db_session.commit()
    
    return None

@sharing_router.put("/{task_id}/share/{user_id}")
def update_share_permission(
    task_id: int,
    user_id: int,
    share_update: TaskShareUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Update permission level"""

    # Get the task
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    # Only owner can unshare
    if task.user_id != current_user.id: # type: ignore
        raise exceptions.UnauthorizedTaskAccessError(task_id=task_id, user_id=current_user.id) # type: ignore
    
    # Find the share
    share = db_session.query(db_models.TaskShare).filter(
        db_models.TaskShare.task_id == task_id,
        db_models.TaskShare.shared_with_user_id == user_id
    ).first()

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task is not shared with this user"
        )
    
    share.permission = share_update.permission # type: ignore
    
    # Delete the share
    db_session.commit()
    db_session.refresh(share)
    
    return {
        "id": share.id,
        "task_id": share.task_id,
        "shared_with_user_id": share.shared_with_user_id,
        "shared_with_username": share.shared_with.username, # <--- Grab it here
        "permission": share.permission,
        "shared_at": share.shared_at
    }

    
