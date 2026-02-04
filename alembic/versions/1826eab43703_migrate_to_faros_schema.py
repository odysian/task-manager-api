"""migrate_to_faros_schema

Revision ID: 1826eab43703
Revises: a144594cccf5
Create Date: 2026-02-03 19:42:32.631847

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1826eab43703"
down_revision: Union[str, Sequence[str], None] = "a144594cccf5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create faros schema and ensure alembic_version is in faros."""
    # Create faros schema if it doesn't exist
    # (This is also handled automatically by env.py, but including for safety)
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS faros"))

    # Handle alembic_version table migration
    # Check if it exists in both schemas
    connection = op.get_bind()

    # Check if it exists in faros schema
    result_faros = connection.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'faros'
            AND table_name = 'alembic_version'
        )
    """
        )
    )
    exists_in_faros = result_faros.scalar()

    # Check if it exists in public schema
    result_public = connection.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'alembic_version'
        )
    """
        )
    )
    exists_in_public = result_public.scalar()

    # Only move if it exists in public but NOT in faros
    # (If it's already in faros, Alembic created it there automatically - leave it alone)
    if exists_in_public and not exists_in_faros:
        op.execute(sa.text("ALTER TABLE public.alembic_version SET SCHEMA faros"))
    # If it exists in both, drop the one in public (shouldn't happen, but handle it)
    elif exists_in_public and exists_in_faros:
        op.execute(sa.text("DROP TABLE public.alembic_version"))
    # If it doesn't exist in either, Alembic will create it automatically in faros
    # (because version_table_schema is set to 'faros' in env.py)

    # Note: The tables in public schema will remain there unused.
    # Since you're okay with fresh data, tables will be created in faros schema
    # automatically when the application starts (via Base.metadata.create_all() or
    # when Alembic runs future migrations).
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema - move alembic_version back to public."""
    # Move alembic_version table back to public schema
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'faros'
            AND table_name = 'alembic_version'
        )
    """
        )
    )
    if result.scalar():
        op.execute(sa.text("ALTER TABLE faros.alembic_version SET SCHEMA public"))
    # ### end Alembic commands ###
