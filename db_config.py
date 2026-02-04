import os

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# Database connection URL
# Format: postgresql://username:password@host:port/database
# For Supabase with schema isolation, include: ?options=-c%20search_path=faros,public
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://task_user:dev_password@localhost:5432/task_manager"
)

# Create engine (handles connection pool)
engine = create_engine(DATABASE_URL, echo=True)

# Session factory (creates database sessions)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All Faros tables live in the "faros" schema (same Supabase DB as other apps, isolated by schema)
# For local development without schema, this will default to "public"
metadata = MetaData(schema="faros")


# Base class for ORM models
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    SQLAlchemy 2.0+ uses DeclarativeBase. Metadata uses schema="faros"
    for deployment (e.g. Supabase + Render, same DB as other projects).
    """

    metadata = metadata


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
