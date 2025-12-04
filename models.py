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

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class FileUploadResponse(BaseModel):
    id: int
    task_id: int
    original_filename: str
    file_size: int
    content_type: str | None
    uploaded_at: datetime

    class Config:
        from_attributes = True

class TaskFileInfo(BaseModel):
    id: int
    original_filename: str
    file_size: int
    content_type: str | None
    uploaded_at: datetime

    class Config:
        from_attributes = True
class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

class Comment(BaseModel):
    """Schema for coment responses"""
    id: int
    task_id: int
    user_id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TaskShareCreate(BaseModel):
    """Request to share a task"""
    shared_with_username: str # Username to share with
    permission: Literal["view", "edit"] = "view"

class TaskShareResponse(BaseModel):
    """Response showing a share"""
    id: int
    task_id: int
    shared_with_user_id: int
    shared_with_username: str # Computer field
    permission: str
    shared_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SharedTaskResponse(BaseModel):
    """Task with sharing context"""
    task: Task
    permission: str # Your permission level
    is_owner: bool # Are you the owner?
    
class TaskShareUpdate(BaseModel):
    """Request to update a share permission"""
    permission: Literal["view", "edit"]
