import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import db_models
from db_config import get_db
from dependencies import get_current_user
from models import NotificationPreferenceResponse, NotificationPreferenceUpdate
from notifications import (get_or_create_preferences,
                           subscribe_user_to_notifications)

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Get current user's notification preferences"""
    prefs = get_or_create_preferences(current_user.id, db_session)  # type: ignore
    return prefs


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    updates: NotificationPreferenceUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Update notification preferences"""
    logger.info(f"Updating notification preferences for user_id={current_user.id}")

    prefs = get_or_create_preferences(current_user.id, db_session)  # type: ignore

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prefs, field, value)

    db_session.commit()
    db_session.refresh(prefs)

    return prefs


@router.post("/subscribe", status_code=status.HTTP_200_OK)
def subscribe_to_notifications(
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Subscribe user's email to SNS topic.
    AWS will send a confirmation email.
    """
    logger.info(f"Subscribing user_id={current_user.id} to notifications")

    # 1. Trigger AWS subscription
    subscription_arn = subscribe_user_to_notifications(current_user.email)  # type: ignore

    if not subscription_arn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe to notifications",
        )

    return {
        "message": "Confirmation email sent. Please check your inbox and confrim subscription.",
        "email": current_user.email,
    }


@router.post("/verify", status_code=status.HTTP_200_OK)
def mark_email_verified(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Mark user's email as verified.

    NOTE: In a real app, this would be a webhook or token-based link.
    For this stage of development, we allow users to self-verify.
    """
    logger.info(f"Marking email verified for user_id={current_user.id}")

    prefs = get_or_create_preferences(current_user.id, db_session)  # type: ignore
    prefs.email_verified = True  # type: ignore

    db_session.commit()

    return {
        "message": "Email verified successfully. You will now receive notifications.",
        "email": current_user.email,
    }
