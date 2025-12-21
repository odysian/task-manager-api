from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .comment import Comment


class TaskCreate(BaseModel):
    """Schema for creating a new task"""

    title: str = Field(min_length=1, max_length=200)  # Can't be empty
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: Optional[date] = None
    tags: list[str] = Field(default_factory=list)
    completed: bool = False
    # Field(default_factory=list) means "if no tags provided, use an empty list []"
    # You can't use = [] directly because that causes Python issues with mutable defaults.

    # Clean up leading/trailing whitespace
    model_config = ConfigDict(str_strip_whitespace=True)


class TaskUpdate(BaseModel):
    """Schema for updating a task"""

    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Literal["low", "medium", "high"]] = None
    due_date: Optional[date] = None
    tags: Optional[list[str]] = None


class Task(BaseModel):
    """Schema for task responses"""

    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: Literal["low", "medium", "high"]
    created_at: datetime
    due_date: Optional[date] = None
    tags: list[str]
    user_id: int
    comments: list["Comment"] = []
    share_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PaginatedTasks(BaseModel):
    """Schema for paginated task list"""

    tasks: list[Task]
    total: int
    page: int
    pages: int


class TaskStats(BaseModel):
    """Schema for task statistics"""

    total: int
    completed: int
    incomplete: int
    by_priority: dict[str, int]
    by_tag: dict[str, int]
    overdue: int
    tasks_shared: int = 0
    comments_posted: int = 0


class BulkTaskUpdate(BaseModel):
    """Schema for bulk updating tasks"""

    task_ids: list[int] = Field(min_length=1)  # Must provide at least one ID
    updates: TaskUpdate  # Reuse the existing TaskUpdate model
