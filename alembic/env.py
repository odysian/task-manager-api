import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

from alembic import context
from db_config import Base
from db_models import Task  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with environment variable if it exists
# This allows migrations to work in Docker where DATABASE_URL is set
# Use attributes dict to bypass ConfigParser interpolation issues with % in URLs
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Set in attributes to avoid ConfigParser % interpolation issues
    # (e.g., %20 in URL query strings)
    if not hasattr(config, "attributes"):
        config.attributes = {}
    config.attributes["sqlalchemy.url"] = database_url

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# Schema we own; all other schemas (auth, storage, rostra, quaero, etc.) are ignored during autogenerate.
# Prevents autogenerate from generating DROP TABLE for Supabase/other apps when run against shared DB.
APP_SCHEMA = target_metadata.schema


def include_object(object, name, type_, reflected, compare_to):
    """
    Restrict autogenerate to APP_SCHEMA only. Ignores auth, storage, rostra, quaero, etc.

    This is CRITICAL for Supabase multi-schema setups. Prevents Alembic from:
    - Generating DROP TABLE for tables in other schemas
    - Modifying tables outside our schema
    - Seeing any objects from other projects

    Returns False to exclude objects from other schemas.
    """
    # Get schema from object (could be Table, Index, etc.)
    object_schema = None
    if hasattr(object, "schema"):
        object_schema = object.schema
    elif hasattr(object, "table") and hasattr(object.table, "schema"):
        # For indexes, constraints, etc. that reference a table
        object_schema = object.table.schema

    # Exclude any object not in our schema
    if object_schema is not None and object_schema != APP_SCHEMA:
        # Log for debugging (can be removed in production)
        import logging

        logger = logging.getLogger("alembic.env")
        # type_ is a string (e.g., "table", "index"), not a type object
        type_name = (
            type_ if isinstance(type_, str) else getattr(type_, "__name__", str(type_))
        )
        logger.debug(
            f"Excluding {type_name} '{name}' from schema '{object_schema}' "
            f"(not in '{APP_SCHEMA}')"
        )
        return False

    # Safety check: Never allow operations on known Supabase schemas
    protected_schemas = {
        "auth",
        "storage",
        "rostra",
        "quaero",
        "extensions",
        "pg_catalog",
        "information_schema",
    }
    if object_schema in protected_schemas:
        import logging

        logger = logging.getLogger("alembic.env")
        # type_ is a string (e.g., "table", "index"), not a type object
        type_name = (
            type_ if isinstance(type_, str) else getattr(type_, "__name__", str(type_))
        )
        logger.warning(
            f"BLOCKED: Attempted to include {type_name} '{name}' "
            f"from protected schema '{object_schema}'"
        )
        return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Get URL from attributes (bypasses ConfigParser) or fall back to config file
    url = None
    if hasattr(config, "attributes") and "sqlalchemy.url" in config.attributes:
        url = config.attributes["sqlalchemy.url"]
    else:
        url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=target_metadata.schema,
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode. Creates faros schema if missing (same pattern as other projects)."""
    configuration = config.get_section(config.config_ini_section, {})
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        configuration["sqlalchemy.url"] = database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=target_metadata.schema,
            include_schemas=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {target_metadata.schema}")
            )
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
