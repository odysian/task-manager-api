import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status


def generate_token(expiration_hours: float) -> tuple[str, datetime]:

    token_str = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

    return token_str, expires_at


def verify_token_expiration(
    expires_at: datetime, error_message: str = "Token has expired"
):

    now = datetime.now(timezone.utc)

    if expires_at < now:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )
