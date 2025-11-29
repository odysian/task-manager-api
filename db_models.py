from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ARRAY, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db_config import Base
from datetime import datetime, timezone

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
    priority = Column(String(20), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    due_date = Column(Date, nullable=True)
    tags = Column(ARRAY(String), default=list, nullable=False)
    notes = Column(String(500), nullable=True) 
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # One task has many file
    files = relationship("TaskFile", back_populates="task", cascade="all, delete-orphan")

    # Many tasks belong to one user
    owner = relationship("User", back_populates="tasks")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # One user has many tasks
    tasks = relationship("Task", back_populates="owner")

class TaskFile(Base):
    __tablename__ = "task_files"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100))
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Each file belongs to one task
    task = relationship("Task", back_populates="files")

