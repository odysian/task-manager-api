from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class Comment(BaseModel):
    """Schema for comment responses"""

    id: int
    task_id: int
    user_id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
