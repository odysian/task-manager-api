import logging
from fastapi import APIRouter, HTTPException, Query, Depends, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from models import Comment, CommentCreate, CommentUpdate
from db_config import get_db
import db_models
import exceptions
from dependencies import get_current_user, require_task_access, TaskPermission

task_comments_router = APIRouter(prefix="/tasks", tags=["comments"])
comments_router = APIRouter(prefix="/comments", tags=["comments"])

logger = logging.getLogger(__name__)

@task_comments_router.post("/{task_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: int,
    comment_data: CommentCreate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Add comments to a task"""
    logger.info(f"Adding comments for task_id={task_id} for user_id={current_user.id}")

    task = db_session.query(db_models.Task).filter(db_models.Task.id == task_id).first()

    if not task:
        logger.warning(f"Task not found: task_id={task_id}")
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    require_task_access(task, current_user, db_session, TaskPermission.VIEW)
    
    comment = db_models.TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        content=comment_data.content
    )

    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)

    logger.info(f"Successfully added comment_id={comment.id} for task_id={task_id}")
    return comment

@task_comments_router.get("/{task_id}/comments", response_model=list[Comment])
def get_comments(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """List all comments attached to a task"""
    logger.info(f"Listing comments for task_id={task_id}, user_id={current_user.id}")

    # Check if task exists and user owns it
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()

    if not task:
        raise exceptions.TaskNotFoundError(task_id=task_id)
    
    require_task_access(task, current_user, db_session, TaskPermission.VIEW)
    
    comments = task.comments
    
    logger.info(f"Found {len(comments)} comments for task_id={task_id}")
    return comments

@comments_router.patch("/{comment_id}", response_model=Comment)
def update_comment(
    comment_id: int,
    comment_data: CommentUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Edit a comment"""
    logger.info(f"Updating comment={comment_id} for user_id={current_user.id}")

    # Find the task
    comment = db_session.query(db_models.TaskComment).filter(
        db_models.TaskComment.id == comment_id).first()

    if not comment:
        logger.warning(f"Comment not found: comment_id={comment_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    require_task_access(comment.task, current_user, db_session, TaskPermission.VIEW)

    # Check if task belongs to current user
    if comment.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access comment_id={comment_id} owned by user_id={comment.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail= f"User {current_user.id} is not authorized to access comment_id={comment_id}"
        )
    
    comment.content = comment_data.content # type: ignore

    db_session.commit()
    db_session.refresh(comment)

    logger.info(f"Comment updated successfully: comment_id={comment_id}, user_id={current_user.id}")

    return comment

@comments_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    """Delete a comment"""
    logger.info(f"Deleting comment={comment_id} for user_id={current_user.id}")

    # Find the task
    comment = db_session.query(db_models.TaskComment).filter(db_models.TaskComment.id == comment_id).first()

    if not comment:
        logger.warning(f"Comment not found: comment_id={comment_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    require_task_access(comment.task, current_user, db_session, TaskPermission.VIEW)

    # Check if task belongs to current user
    if comment.user_id != current_user.id and comment.task.user_id != current_user.id: # type: ignore
        logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access comment_id={comment_id} owned by user_id={comment.user_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail= f"User {current_user.id} is not authorized to access comment_id={comment_id}")

    db_session.delete(comment)
    db_session.commit()

    logger.info(f"Comment deleted successfully: comment_id={comment_id}")

    return None

