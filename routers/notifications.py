import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import db_models
from db_config import get_db
from dependencies import get_current_user
from models import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    VerifyEmailRequest,
)
from notifications import (
    NotificationType,
    get_or_create_preferences,
    send_direct_email,
    send_notification,
    subscribe_user_to_notifications,
)

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
    request: VerifyEmailRequest,
    db_session: Session = Depends(get_db),
):
    """
    Verify email using token from email link.
    Does not require auth (user clicks from email).
    """
    logger.info(f"Verifying email with token: {request.token[:10]}...")

    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.verification_code == request.token)
        .first()
    )

    if not user:
        logger.warning(f"Invalid token: {request.token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    if user.verification_expires < datetime.now(timezone.utc):  # type: ignore
        logger.warning(f"Expired token for user_id={user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired. Please request a new one.",
        )

    user.email_verified = True  # type: ignore
    user.verification_code = None  # type: ignore
    user.verification_expires = None  # type: ignore

    prefs = get_or_create_preferences(user.id, db_session)  # type: ignore
    prefs.email_verified = True  # type: ignore

    db_session.commit()

    logger.info(f"Email verified successfully for user_id={user.id}")

    return {
        "message": "Email verified successfully",
        "username": user.username,
    }


@router.post("/send-verification", status_code=status.HTTP_200_OK)
def send_verification_email(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Generate verification token and send email.
    User must be authenticated to request verification
    """
    logger.info(f"Sending verification email to user_id={current_user.id}")

    # Generate token
    token = secrets.token_urlsafe(32)

    # Store token with 24hr exp
    current_user.verification_code = token  # type: ignore
    current_user.verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)  # type: ignore
    db_session.commit()

    # Build verification URL
    verification_url = f"http://localhost:5173/verify?token={token}"

    # Email content
    subject = "Verify your FAROS email address"
    body_text = f"""
Hi {current_user.username},

Please verify your email address to enable notifications.

Click here to verify: {verification_url}

This link expires in 24 hours.

If you didn't request this, you can safely ignore this email.

---
FAROS Task Manager
    """

    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Hi {current_user.username},</h2>
    <p>Please verify your email address to enable notifications.</p>
    <p>
        <a href="{verification_url}" 
           style="background-color: #10b981; color: white; padding: 12px 24px; 
                  text-decoration: none; border-radius: 6px; display: inline-block;">
            Verify Email
        </a>
    </p>
    <p style="color: #666; font-size: 14px;">
        This link expires in 24 hours.
    </p>
    <p style="color: #666; font-size: 12px;">
        If you didn't request this, you can safely ignore this email.
    </p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="color: #999; font-size: 12px;">FAROS Task Manager</p>
</body>
</html>
    """

    success = send_direct_email(
        recipient_email=current_user.email,  # type: ignore
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email",
        )

    return {
        "message": "Verification email sent",
        "email": current_user.email,
        "expires_in": "24 hours",
    }
