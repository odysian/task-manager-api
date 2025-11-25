from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, date

# --- Pydantic Models (Schemas) ---

class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    title: str = Field(min_length=1, max_length=200) # Can't be empty
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: Optional[date] = None
    tags: list[str] = Field(default_factory=list)
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

    model_config = ConfigDict(from_attributes=True)

class TaskStats(BaseModel):
    """Schema for task statistics"""
    total: int
    completed: int
    incomplete: int
    by_priority: dict[str, int]
    by_tag: dict[str, int]
    overdue: int

class BulkTaskUpdate(BaseModel):
    """Schema for bulk updating tasks"""
    task_ids: list[int] = Field(min_length=1)   # Must provide at least one ID
    updates: TaskUpdate   # Reuse the existing TaskUpdate model

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