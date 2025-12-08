import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Database connection URL
# Format: postgresql://username:password@host:port/database
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://task_user:dev_password@localhost:5432/task_manager"
)

# Create engine (handles connection pool)
engine = create_engine(DATABASE_URL, echo=True)

# Session factory (creates database sessions)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
