from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from db_config import get_db
import db_models
from models import UserCreate, UserResponse, UserLogin, Token
from auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db_session: Session = Depends(get_db)):
    """
    Register a new user account
    - Validates username and email are unique
    - Hashes password before storing
    - Returns created user (without password)
    """
    # Check if username already exists
    existing_user = db_session.query(db_models.User).filter(db_models.User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = db_session.query(db_models.User).filter(db_models.User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Hash the password
    hashed_password = hash_password(user_data.password)

    # Create new user
    new_user = db_models.User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )

    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)

    return new_user

@router.post("/login", response_model=Token)
def login_user(login_data: UserLogin, db_session: Session = Depends(get_db)):
    """
    Login with username and password
    - Validates credentials
    - Returns JWT access token
    - Token must be included in Authorization header for protected routes
    """
    # Look up user by username
    user = db_session.query(db_models.User).filter(
        db_models.User.username == login_data.username
    ).first()

    # Check if user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password): # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
