import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import db_models
from core.tokens import generate_token, verify_token_expiration
from db_config import get_db
from dependencies import get_current_user
from schemas.auth import VerifyEmailRequest
from schemas.notification import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)
from services.notifications import (
    get_or_create_preferences,
    send_direct_email,
    subscribe_user_to_notifications,
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

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
    Subscribe user's email to notifications.

    With Resend: No subscription needed - user is automatically ready to receive emails.
    With AWS SNS: Would send confirmation email (not implemented for simplicity).
    """
    logger.info(f"Subscribing user_id={current_user.id} to notifications")

    # Subscribe (with Resend, this is a no-op but kept for API compatibility)
    subscription_arn = subscribe_user_to_notifications(current_user.email)  # type: ignore

    if not subscription_arn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe to notifications",
        )

    return {
        "message": "You are now subscribed to notifications. You will receive emails based on your preferences.",
        "email": current_user.email,
    }


def _verify_email_token(token: str, db_session: Session):
    """
    Internal function to verify email token.
    Returns user if valid, raises HTTPException if invalid.
    """
    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.verification_code == token)
        .first()
    )

    if not user:
        logger.warning("Invalid email verification token attempt")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    verify_token_expiration(
        user.verification_expires,  # type: ignore
        error_message="Verification link has expired. Please request a new one.",
    )

    user.email_verified = True  # type: ignore
    user.verification_code = None  # type: ignore
    user.verification_expires = None  # type: ignore

    prefs = get_or_create_preferences(user.id, db_session)  # type: ignore
    prefs.email_verified = True  # type: ignore

    db_session.commit()

    logger.info(f"Email verified successfully for user_id={user.id}")
    return user


@router.get("/verify", status_code=status.HTTP_200_OK)
def verify_email_get(
    token: str,
    db_session: Session = Depends(get_db),
):
    """
    Verify email using token from email link (GET endpoint for direct clicks).
    Does not require auth (user clicks from email).
    """
    logger.info("Email verification attempt (GET)")

    user = _verify_email_token(token, db_session)

    # Redirect to frontend - email is already verified by this GET endpoint
    # Redirect to login with success message (frontend can show toast/notification)
    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url=f"{FRONTEND_URL}/login?emailVerified=true&username={user.username}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/verify", status_code=status.HTTP_200_OK)
def mark_email_verified(
    request: VerifyEmailRequest,
    db_session: Session = Depends(get_db),
):
    """
    Verify email using token from email link (POST endpoint for API calls).
    Does not require auth (user clicks from email).
    """
    logger.info("Email verification attempt (POST)")

    user = _verify_email_token(request.token, db_session)

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
    token, expires_at = generate_token(expiration_hours=24)

    # Store token with 24hr exp
    current_user.verification_code = token  # type: ignore
    current_user.verification_expires = expires_at  # type: ignore
    db_session.commit()

    # Build verification URL - point directly to frontend
    # Frontend will handle the verification via POST to /notifications/verify
    verification_url = f"{FRONTEND_URL}/verify?token={token}"

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
