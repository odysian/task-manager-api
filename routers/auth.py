import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

import db_models
import exceptions
from auth import create_access_token, hash_password, verify_password
from db_config import get_db
from models import Token, UserCreate, UserLogin, UserResponse
from rate_limit_config import limiter

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
