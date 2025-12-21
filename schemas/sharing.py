from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .task import Task


class TaskShareCreate(BaseModel):
    """Request to share a task"""

    shared_with_username: str  # Username to share with
    permission: Literal["view", "edit"] = "view"


class TaskShareResponse(BaseModel):
    """Response showing a share"""

    id: int
    task_id: int
    shared_with_user_id: int
    shared_with_username: str  # Computer field
    permission: str
    shared_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SharedTaskResponse(BaseModel):
    """Task with sharing context"""

    task: Task
    permission: str  # Your permission level
    is_owner: bool  # Are you the owner?
    owner_username: str


class TaskShareUpdate(BaseModel):
    """Request to update a share permission"""

    permission: Literal["view", "edit"]
