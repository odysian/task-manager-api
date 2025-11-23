from pydantic import BaseModel, Field
from typing import Optional, Literal

# --- Pydantic Models (Schemas) ---

class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    title: str = Field(min_length=1, max_length=200) # Can't be empty
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: Literal["low", "medium", "high"] = "medium"

    # Clean up leading/trailing whitespace
    class Config:
        str_strip_whitespace = True


class TaskUpdate(BaseModel):
    """Schema for updating a task"""
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Literal["low", "medium", "high"]] = None


class Task(BaseModel):
    """Schema for task responses"""
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: Literal["low", "medium", "high"]