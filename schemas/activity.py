from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ActivityLogResponse(BaseModel):
    """Response model for activity log entries."""

    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: int
    details: Optional[dict[str, Any]] = None
    created_at: datetime
    username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityLogCreate(BaseModel):
    """Internal model for creating activity logs (not exposed via API)."""

    user_id: int
    action: str
    resource_type: str
    resource_id: int
    details: Optional[dict[str, Any]] = None


class ActivityQuery(BaseModel):
    """Query parameters for filtering activity logs."""

    resource_type: Optional[str] = None
    action: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class TaskActivityResponse(BaseModel):
    """Activity log with enhanced context for task timeline."""

    id: int
    user_id: int
    username: str
    action: str
    resource_type: str
    resource_id: int
    details: dict[str, Any]
    created_at: datetime

    # Human-readable summary
    summary: str

    model_config = ConfigDict(from_attributes=True)
