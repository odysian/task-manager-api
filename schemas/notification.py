from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating preferences (all optional)"""

    email_enabled: Optional[bool] = None
    task_shared_with_me: Optional[bool] = None
    task_completed: Optional[bool] = None
    comment_on_my_task: Optional[bool] = None
    task_due_soon: Optional[bool] = None


class NotificationPreferenceResponse(BaseModel):
    """Schema for reading preferences"""

    user_id: int
    email_verified: bool
    email_enabled: bool
    task_shared_with_me: bool
    task_completed: bool
    comment_on_my_task: bool
    task_due_soon: bool
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
