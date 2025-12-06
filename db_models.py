from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
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

    # Relationships
    files = relationship("TaskFile", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    owner = relationship("User", back_populates="tasks")
    shares = relationship("TaskShare", back_populates="task", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tasks = relationship("Task", back_populates="owner")
    notification_preferences = relationship(
        "NotificationPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

class TaskFile(Base):
    __tablename__ = "task_files"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100))
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    task = relationship("Task", back_populates="files")

class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    task = relationship("Task", back_populates="comments")
    author = relationship("User")

class TaskShare(Base):
    __tablename__ = "task_shares"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String(20), nullable=False)
    shared_at = Column(DateTime, server_default=func.now())
    shared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    task = relationship("Task", back_populates="shares")
    shared_with = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])

    # Unique constraint: Can't share same task with same user twice
    __table_args__ = (
        UniqueConstraint('task_id', 'shared_with_user_id', name='unique_task_share'),
    )

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    # Link directly to User ID (One-to-One)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    
    # Status
    email_verified = Column(Boolean, default=False)
    email_enabled = Column(Boolean, default=True) # Master switch
    
    # Granular Preferences (Defaults to True)
    task_shared_with_me = Column(Boolean, default=True)
    task_completed = Column(Boolean, default=True)
    comment_on_my_task = Column(Boolean, default=True)
    task_due_soon = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship back to User
    user = relationship("User", back_populates="notification_preferences")                 
    

