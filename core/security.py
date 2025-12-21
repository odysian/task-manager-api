import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

# Get and validate settings from environment
_secret_key = os.getenv("SECRET_KEY")
_algorithm = os.getenv("ALGORITHM")

if not _secret_key:
    raise ValueError("SECRET_KEY must be set in .env file")
if not _algorithm:
    raise ValueError("ALGORITHM must be set in .env file")

SECRET_KEY: str = _secret_key
ALGORITHM: str = _algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))


# Configure bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Has a plain password using bcrypt.
    Args:
        password: Plain text password from user
    Returns:
        Hashed password string (safe to store in db)
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    Args:
        plain_password: Password provided by user during login
        hashed_password: Hashed password from database
    Returns:
        True if passwords match, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """
    Create a JWT access token.
    Args:
        data: Dictionary containing user information (usually {"sub": username})
    Returns:
        Encoded JWT token string
    """

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> dict | None:
    """
    Verify and decode a JWT access token.
    Args:
        token: JWT token string
    Returns:
        Decoded token payload if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
