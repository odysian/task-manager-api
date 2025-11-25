# Task Manager API - Learning Project

A learning project building a REST API with FastAPI and PostgreSQL. This tracks my progression from in-memory storage to a production-ready database setup.

## What I've Learned

**Phase 1: FastAPI Fundamentals**
- Building APIs with FastAPI
- Data validation with Pydantic
- REST principles (CRUD operations, proper HTTP methods/status codes)
- Query parameters for filtering, search, sorting, and pagination
- Working with dates and timestamps in Python
- Code organization (separating models, routes, database logic)

**Phase 2: Database & Persistence**
- PostgreSQL installation and configuration
- SQL fundamentals (DDL and DML)
- SQLAlchemy ORM (models, sessions, queries)
- Database connection management and dependency injection
- Alembic migrations for schema versioning
- Migrating from in-memory to persistent storage

## Current Features

- Full CRUD operations for tasks
- Advanced filtering (completion status, priority, tags, date ranges)
- Text search across titles and descriptions
- Multi-field sorting (ascending/descending)
- Pagination with skip/limit
- Tag management (add/remove individual tags)
- Due dates with overdue detection
- Statistics endpoint for task analytics
- Bulk update operations
- PostgreSQL database with SQLAlchemy ORM
- Database migrations with Alembic

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL

### Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn pydantic sqlalchemy psycopg2-binary alembic

# Set up PostgreSQL database
sudo -i -u postgres
psql
CREATE DATABASE task_manager;
CREATE USER task_user WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE task_manager TO task_user;
\q
exit

# Run migrations
alembic upgrade head

# Seed sample data (optional)
python seed_data.py

# Run the API
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` to see the interactive API documentation.

## Project Structure
```
task-manager-api/
├── main.py              # App setup and entry point
├── models.py            # Pydantic models (API validation)
├── db_models.py         # SQLAlchemy models (database tables)
├── db_config.py         # Database connection and session management
├── create_tables.py     # Initial table creation script
├── seed_data.py         # Sample data for testing
├── alembic/             # Database migrations
│   └── versions/        # Migration files
├── alembic.ini          # Alembic configuration
├── routers/
│   └── tasks.py         # All task-related endpoints
└── notes/
    ├── week1-2-concepts.md    # FastAPI concepts cheatsheet
    └── week3-4-database-concepts.md  # Database concepts cheatsheet
```

## Example Usage
```bash
# Get all tasks with filtering
GET /tasks?priority=high&completed=false&sort_by=due_date

# Search for tasks
GET /tasks?search=fastapi

# Get overdue tasks
GET /tasks?overdue=true

# Create a task
POST /tasks
{
  "title": "Learn SQLAlchemy",
  "description": "Master ORM concepts",
  "priority": "high",
  "due_date": "2025-12-01",
  "tags": ["learning", "backend"]
}

# Add tags to existing task
POST /tasks/1/tags
["urgent", "review"]

# Bulk update multiple tasks
PATCH /tasks/bulk
{
  "task_ids": [1, 2, 3],
  "updates": {"completed": true}
}

# Get task statistics
GET /tasks/stats
```

## Database Migrations
```bash
# Generate migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history

# View current migration
alembic current
```

## What I'm Working On Next

**Authentication & Authorization**
- User registration and login
- JWT token authentication
- Password hashing with bcrypt
- Protected routes
- User-specific task access
- Proper security patterns

## Learning Notes

- Data now persists in PostgreSQL (survives server restarts)
- Using SQLAlchemy ORM instead of raw SQL
- Alembic handles schema changes safely
- Proper dependency injection for database sessions
- No authentication yet—that's the next phase
- Following a structured 16-week backend development roadmap

## Resources I'm Using

- [FastAPI Official Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [PostgreSQL Tutorial](https://www.postgresqltutorial.com/)
- [Real Python](https://realpython.com/)