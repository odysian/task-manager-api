import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

import db_models
from core import exceptions
from core.redis_config import invalidate_user_cache
from db_config import get_db
from dependencies import TaskPermission, get_current_user, require_task_access
from schemas.comment import Comment, CommentCreate, CommentUpdate
from services import activity_service
from services.background_tasks import notify_comment_added

task_comments_router = APIRouter(prefix="/tasks", tags=["comments"])
comments_router = APIRouter(prefix="/comments", tags=["comments"])

logger = logging.getLogger(__name__)


@task_comments_router.post(
    "/{task_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED
)
def add_comment(
    task_id: int,
    comment_data: CommentCreate,
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Add comments to a task"""
    logger.info(f"Adding comments for task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.VIEW)

    comment = db_models.TaskComment(
        task_id=task_id, user_id=current_user.id, content=comment_data.content
    )

    db_session.add(comment)
    db_session.flush()

    activity_service.log_comment_created(
        db_session=db_session, user_id=current_user.id, comment=comment  # type: ignore
    )
    db_session.commit()
    db_session.refresh(comment)

    if task.user_id != current_user.id:  # type:ignore
        background_tasks.add_task(
            notify_comment_added,
            recipient_user_id=task.user_id,  # type:ignore
            recipient_email=task.owner.email,
            task_title=task.title,  # type:ignore
            commenter_username=current_user.username,  # type:ignore
            comment_content=comment_data.content,
        )

    invalidate_user_cache(current_user.id)  # type: ignore

    logger.info(f"Successfully added comment_id={comment.id} for task_id={task_id}")
    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "username": current_user.username,
    }


@task_comments_router.get("/{task_id}/comments", response_model=list[Comment])
def get_comments(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """List all comments attached to a task"""
    logger.info(f"Listing comments for task_id={task_id}, user_id={current_user.id}")

    # Check if task exists and user owns it
    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)

    require_task_access(task, current_user, db_session, TaskPermission.VIEW)

    comments = (
        db_session.query(db_models.TaskComment)
        .options(joinedload(db_models.TaskComment.user))
        .filter(db_models.TaskComment.task_id == task_id)
        .order_by(db_models.TaskComment.created_at)
        .all()
    )

    logger.info(f"Found {len(comments)} comments for task_id={task_id}")
    return [
        {
            "id": c.id,
            "task_id": c.task_id,
            "user_id": c.user_id,
            "content": c.content,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "username": c.user.username if c.user else None,
        }
        for c in comments
    ]


@comments_router.patch("/{comment_id}", response_model=Comment)
def update_comment(
    comment_id: int,
    comment_data: CommentUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Edit a comment"""
    logger.info(f"Updating comment={comment_id} for user_id={current_user.id}")

    # Find the task
    comment = (
        db_session.query(db_models.TaskComment)
        .filter(db_models.TaskComment.id == comment_id)
        .first()
    )

    if not comment:
        logger.warning(f"Comment not found: comment_id={comment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    require_task_access(comment.task, current_user, db_session, TaskPermission.VIEW)

    # Check if task belongs to current user
    if comment.user_id != current_user.id:  # type: ignore
        logger.warning(
            f"Unauthorized access attempt: user_id={current_user.id} "
            f"tried to access comment_id={comment_id} owned by user_id={comment.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User {current_user.id} is not authorized to access comment_id={comment_id}",
        )

    old_content = comment.content

    comment.content = comment_data.content  # type: ignore

    new_content = comment.content

    activity_service.log_comment_updated(
        db_session=db_session,
        user_id=current_user.id,  # type: ignore
        comment=comment,
        old_content=old_content,  # type: ignore
        new_content=new_content,  # type: ignore
    )

    db_session.commit()
    db_session.refresh(comment)

    logger.info(
        f"Comment updated successfully: comment_id={comment_id}, user_id={current_user.id}"
    )

    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "username": comment.user.username if comment.user else None,
    }


@comments_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Delete a comment"""
    logger.info(f"Deleting comment={comment_id} for user_id={current_user.id}")

    # Find the task
    comment = (
        db_session.query(db_models.TaskComment)
        .filter(db_models.TaskComment.id == comment_id)
        .first()
    )

    if not comment:
        logger.warning(f"Comment not found: comment_id={comment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    require_task_access(comment.task, current_user, db_session, TaskPermission.VIEW)

    # Check if task belongs to current user
    if current_user.id not in (comment.user_id, comment.task.user_id):  # type: ignore
        logger.warning(
            f"Unauthorized access attempt: user_id={current_user.id} "
            f"tried to access comment_id={comment_id} owned by user_id={comment.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User {current_user.id} is not authorized to "
            f"access comment_id={comment_id}",
        )

    activity_service.log_comment_deleted(
        db_session=db_session, user_id=current_user.id, comment=comment  # type: ignore
    )
    db_session.delete(comment)
    db_session.commit()

    invalidate_user_cache(current_user.id)  # type: ignore

    logger.info(f"Comment deleted successfully: comment_id={comment_id}")
