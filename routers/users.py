import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import db_models
from core.security import hash_password, verify_password
from db_config import get_db
from dependencies import get_current_user
from schemas.auth import PasswordChange, UserProfile

router = APIRouter(prefix="/users", tags=["users"])

logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: db_models.User = Depends(get_current_user)):
    """Get the currently logged-in user's profile"""
    return current_user


@router.patch("/me/change-password")
def change_password(
    password_data: PasswordChange,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Change a user's password"""

    logger.info(f"Attempting to change password for user_id={current_user.id}")

    if not verify_password(
        password_data.current_password, current_user.hashed_password  # type: ignore
    ):
        logger.warning("Password change failed: Current password incorrect.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    new_hashed_password = hash_password(password_data.new_password)

    current_user.hashed_password = new_hashed_password  # type: ignore

    db_session.commit()
    db_session.refresh(current_user)

    logger.info(f"Password changed successfully for user_id={current_user.id}")

    return {"message": "Password changed successfully"}


@router.get("/search")
def search_users(
    query: str = Query(..., min_length=1, description="Username to search for"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Search for users by username.

    Returns list of users matching the search query.
    Excluded the current user from results.
    Case-insensitive search.
    """

    logger.info(f"User search: query='{query}', user_id={current_user.id}")

    users = (
        db_session.query(db_models.User)
        .filter(db_models.User.username.ilike(f"%{query}%"))
        .filter(db_models.User.id != current_user.id)
        .limit(limit)
        .all()
    )

    logger.info(f"Found {len(users)} users matching '{query}'")

    return [
        {
            "id": user.id,
            "username": user.username,
        }
        for user in users
    ]
