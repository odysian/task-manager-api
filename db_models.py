from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey,
                        Index, Integer, String, UniqueConstraint)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db_config import Base


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
    files = relationship(
        "TaskFile", back_populates="task", cascade="all, delete-orphan"
    )
    comments = relationship(
        "TaskComment", back_populates="task", cascade="all, delete-orphan"
    )
    owner = relationship("User", back_populates="tasks")
    shares = relationship(
        "TaskShare", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Task(id={self.id}, title={self.title[:30]}, user={self.user_id}, completed={self.completed})>"


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
        cascade="all, delete-orphan",
    )
    activity_logs = relationship(
        "ActivityLog", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class TaskFile(Base):
    __tablename__ = "task_files"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
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
    task_id = Column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
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
        UniqueConstraint("task_id", "shared_with_user_id", name="unique_task_share"),
    )

    def __repr__(self):
        return f"<TaskShare(task={self.task_id}, shared_with={self.shared_with_user_id}, permission={self.permission})>"


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    # Link directly to User ID (One-to-One)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    # Status
    email_verified = Column(Boolean, default=False)
    email_enabled = Column(Boolean, default=True)  # Master switch

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


class ActivityLog(Base):
    """
    Tracks all user actions in the system for audit and transparency.
    Uses polymorphic pattern to track actions on any resource type.
    """

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="activity_logs")

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_activity_logs_user_id", "user_id"),
        Index("ix_activity_logs_created_at", "created_at"),
        Index("ix_activity_logs_resource", "resource_type", "resource_id"),
        Index("ix_activity_logs_action", "action"),
    )

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, user={self.user_id}, action={self.action}, resource={self.resource_type}:{self.resource_id})>"
