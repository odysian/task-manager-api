"""set_notification_preference_defaults

Revision ID: ea39397b99b1
Revises: 6598de72eb49
Create Date: 2025-12-18 16:56:37.972397

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea39397b99b1"
down_revision: Union[str, Sequence[str], None] = "6598de72eb49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set proper defaults for all notification preference columns."""

    # Add SQL defaults to all columns
    op.alter_column(
        "notification_preferences", "email_verified", server_default="false"
    )
    op.alter_column("notification_preferences", "email_enabled", server_default="true")
    op.alter_column(
        "notification_preferences", "task_shared_with_me", server_default="true"
    )
    op.alter_column(
        "notification_preferences", "task_completed", server_default="false"
    )
    op.alter_column(
        "notification_preferences", "comment_on_my_task", server_default="true"
    )
    op.alter_column("notification_preferences", "task_due_soon", server_default="true")

    # Update existing rows to have proper values (NULL → defaults)
    op.execute(
        """
        UPDATE notification_preferences
        SET 
            email_verified = COALESCE(email_verified, false),
            email_enabled = COALESCE(email_enabled, true),
            task_shared_with_me = COALESCE(task_shared_with_me, true),
            task_completed = COALESCE(task_completed, false),
            comment_on_my_task = COALESCE(comment_on_my_task, true),
            task_due_soon = COALESCE(task_due_soon, true)
    """
    )


def downgrade() -> None:
    """Remove SQL defaults."""

    # Remove all defaults
    op.alter_column("notification_preferences", "email_verified", server_default=None)
    op.alter_column("notification_preferences", "email_enabled", server_default=None)
    op.alter_column(
        "notification_preferences", "task_shared_with_me", server_default=None
    )
    op.alter_column("notification_preferences", "task_completed", server_default=None)
    op.alter_column(
        "notification_preferences", "comment_on_my_task", server_default=None
    )
    op.alter_column("notification_preferences", "task_due_soon", server_default=None)
