import logging
import os

import boto3
from botocore.exceptions import ClientError
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import db_models
from core.security import hash_password, verify_password
from core.storage import S3_BUCKET_NAME, s3_client
from db_config import get_db
from dependencies import get_current_user
from schemas.auth import PasswordChange, UserProfile

router = APIRouter(prefix="/users", tags=["users"])

logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: db_models.User = Depends(get_current_user)):
    """Get the currently logged-in user's profile"""
    return current_user


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Upload a profile picture for the current user"""

    if not file.content_type.startswith("image/"):  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image"
        )

    file_ext = file.filename.split(".")[-1]  # type: ignore
    s3_key = f"avatars/user_{current_user.id}_avatar.{file_ext}"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=await file.read(),
            ContentType=file.content_type,
        )
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar",
        )

    avatar_url = f"/users/{current_user.id}/avatar.{file_ext}"

    current_user.avatar_url = avatar_url  # type: ignore
    db_session.commit()

    return {"avatar_url": avatar_url}


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


@router.get("/{user_id}/avatar.{ext}")
def get_user_avatar(user_id: int, ext: str, db_session: Session = Depends(get_db)):
    """Stream the avatar image from S3"""

    user = db_session.query(db_models.User).filter(db_models.User.id == user_id).first()

    if not user or not user.avatar_url:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found"
        )

    s3_key = f"avatars/user_{user_id}_avatar.{ext}"

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return StreamingResponse(response["Body"], media_type=response["ContentType"])
    except ClientError:
        raise HTTPException(404, "Avatar not found")
