from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Schema to create user"""

    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=100)
    password: str = Field(min_length=8, max_length=100)


class UserResponse(BaseModel):
    """Schema for return response for users"""

    id: int
    username: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetComplete(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=100)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)


class UserProfile(BaseModel):
    """Profile data for the current user"""

    id: int
    username: str
    email: str
    avatar_url: Optional[str] = None
    email_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class VerifyEmailRequest(BaseModel):
    token: str
