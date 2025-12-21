from datetime import datetime

from pydantic import BaseModel


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
