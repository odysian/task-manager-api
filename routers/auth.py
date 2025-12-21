import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import db_models
from core import exceptions
from core.rate_limit_config import limiter
from core.security import create_access_token, hash_password, verify_password
from core.tokens import generate_token, verify_token_expiration
from db_config import get_db
from schemas.auth import (
    PasswordResetComplete,
    PasswordResetRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from services.notifications import send_direct_email

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/hour")  # Only 10 registrations per hour per IP
def register_user(
    request: Request,  # pylint: disable=unused-argument
    user_data: UserCreate,
    db_session: Session = Depends(get_db),
):
    """
    Register a new user account
    - Validates username and email are unique
    - Hashes password before storing
    - Returns created user (without password)
    - Rate limited to 10 attempts per hour per IP
    """

    logger.info(
        f"Registration attempt for username: {user_data.username}, email: {user_data.email}"
    )

    # Check if username already exists
    existing_user = (
        db_session.query(db_models.User)
        .filter(db_models.User.username == user_data.username)
        .first()
    )
    if existing_user:
        logger.warning(
            f"Registration failed: username '{user_data.username}' already exists"
        )
        raise exceptions.DuplicateUserError(field="username", value=user_data.username)

    # Check if email already exists
    existing_email = (
        db_session.query(db_models.User)
        .filter(db_models.User.email == user_data.email)
        .first()
    )
    if existing_email:
        logger.warning(f"Registration failed: email '{user_data.email}' already exists")
        raise exceptions.DuplicateUserError(field="email", value=user_data.email)

    # Hash the password
    hashed_password = hash_password(user_data.password)

    # Create new user
    new_user = db_models.User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
    )

    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)

    logger.info(
        f"User registered successfully: username='{new_user.username}', user_id={new_user.id}"
    )

    return new_user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")  # Only 5 login attempts per minute
def login_user(
    request: Request,  # pylint: disable=unused-argument
    login_data: UserLogin,
    db_session: Session = Depends(get_db),
):
    """
    Login with username and password
    - Validates credentials
    - Returns JWT access token
    - Token must be included in Authorization header for protected routes
    - Rate limited to 5 attempts per minute
    """

    logger.info(
        f"Login attempt for username: {login_data.username} (rate limit: 5/minute)"
    )

    # Look up user by username
    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.username == login_data.username)
        .first()
    )

    # Check if user exists and if password is correct
    if not user or not verify_password(login_data.password, user.hashed_password):  # type: ignore
        logger.warning(
            f"Login failed for username: {login_data.username} (invalid credentials)"
        )
        raise exceptions.InvalidCredentialsError()

    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    logger.info(f"Login successful for user: {user.username} (user_id={user.id})")

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/password-reset/request")
@limiter.limit("1/minute")
def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request,
    db_session: Session = Depends(get_db),
):
    """
    Requests a password reset.

    Sends request to email if found in database.
    """

    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.email == reset_request.email)
        .first()
    )

    # Check if email exists, return same message regardless
    if not user:
        return {"message": "If email exists, password reset sent."}

    logger.info(f"Password reset requested for user_id={user.id}")

    token_str, expires_at = generate_token(expiration_hours=0.5)
    user.password_reset_token = token_str  # type: ignore
    user.password_reset_token_expires = expires_at  # type: ignore
    db_session.commit()

    # Build password reset URL
    reset_url = f"{FRONTEND_URL}/password-reset?token={token_str}"

    # Email content
    subject = "Reset your FAROS password"
    body_text = f"""
We received a request to reset the password for your FAROS account.

Click here to reset: {reset_url}

This link expires in 30 minutes.

If you didn't request this, please ignore this email. Your password will not be changed.

---
FAROS Task Manager
    """

    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2>Password Reset Request</h2>
    <p>We received a request to reset the password for your FAROS account.</p>
    <p>
        <a href="{reset_url}"
           style="background-color: #10b981; color: white; padding: 12px 24px; 
                  text-decoration: none; border-radius: 6px; display: inline-block;">
            Reset Password
        </a>
    </p>
    <p style="color: #666; font-size: 14px;">
        This link expires in 30 minutes.
    </p>
    <p style="color: #666; font-size: 12px;">
        If you didn't request this, please ignore this email. Your password will not be changed.
    </p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="color: #999; font-size: 12px;">FAROS Task Manager</p>
</body>
</html>
    """

    success = send_direct_email(
        recipient_email=user.email,  # type: ignore
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )

    if not success:
        logger.error(f"Failed to send password reset email to user_id={user.id}")
        return {"message": "If email exists, password reset sent"}

    logger.info(f"Password reset email sent successfully to user_id={user.id}")
    return {"message": "If email exists, password reset sent"}


@router.post("/password-reset/verify")
def verify_password_reset(
    request: PasswordResetComplete,
    db_session: Session = Depends(get_db),
):
    """Verify password reset request using token from email"""

    user = (
        db_session.query(db_models.User)
        .filter(db_models.User.password_reset_token == request.token)
        .first()
    )

    if not user:
        logger.warning("Invalid password reset token attempt")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    verify_token_expiration(
        user.password_reset_token_expires,  # type: ignore
        error_message="Password reset link has expired. Please request a new one.",
    )

    logger.info(f"Password reset successful for user_id={user.id}")

    user.hashed_password = hash_password(request.new_password)  # type: ignore
    user.password_reset_token = None  # type: ignore
    user.password_reset_token_expires = None  # type: ignore

    db_session.commit()

    return {
        "message": "Password updated successfully. You can now log in with your new password."
    }
