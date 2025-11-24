# Week 3-4 Database Concepts Cheatsheet

Personal reference guide for PostgreSQL, SQLAlchemy, and Alembic.

---

## PostgreSQL Basics

### What is PostgreSQL?
- Open-source relational database (RDBMS)
- Industry standard, used by companies like Instagram, Spotify, Reddit
- Stores data in tables with rows and columns
- Supports complex queries, relationships, transactions
- Data persists even when server restarts (unlike in-memory)

### Key Concepts
- **Database** - Container for tables (e.g., `task_manager`)
- **Table** - Structured data storage (e.g., `tasks`)
- **Row** - Single record (e.g., one task)
- **Column** - Field in a record (e.g., `title`, `priority`)
- **Primary Key** - Unique identifier for rows (e.g., `id`)
- **Schema** - Organization structure (default is `public`)

### Common Commands (psql)
```bash
# Connect to database
psql -U task_user -d task_manager -h localhost

# List databases
\l

# List tables
\dt

# Describe table structure
\d tasks

# Show table with data
SELECT * FROM tasks;

# Quit
\q
```

---

## SQL Refresher (DDL - Data Definition Language)

### Create Table
```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,              -- Auto-incrementing ID
    title VARCHAR(200) NOT NULL,        -- String, required
    description TEXT,                   -- Longer text, optional
    completed BOOLEAN DEFAULT FALSE,    -- Boolean with default
    priority VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date DATE,
    tags TEXT[]                         -- Array of strings (PostgreSQL)
);
```

**Column types:**
- `SERIAL` - Auto-incrementing integer
- `INTEGER` - Whole number
- `VARCHAR(n)` - String with max length
- `TEXT` - Unlimited text
- `BOOLEAN` - true/false
- `TIMESTAMP` - Date and time
- `DATE` - Just the date
- `TEXT[]` - Array

**Constraints:**
- `PRIMARY KEY` - Unique identifier, not null
- `NOT NULL` - Must have a value
- `DEFAULT` - Value if not provided
- `UNIQUE` - No duplicates allowed

### Modify Table
```sql
-- Add column
ALTER TABLE tasks ADD COLUMN notes VARCHAR(500);

-- Drop column
ALTER TABLE tasks DROP COLUMN notes;

-- Rename column
ALTER TABLE tasks RENAME COLUMN notes TO comments;

-- Change column type
ALTER TABLE tasks ALTER COLUMN priority TYPE VARCHAR(50);
```

### Delete Table
```sql
DROP TABLE tasks;  -- Deletes table and all data!
```

---

## SQL DML (Data Manipulation Language)

### Insert
```sql
INSERT INTO tasks (title, priority, tags)
VALUES ('Learn SQL', 'high', ARRAY['learning', 'database']);
```

### Select
```sql
-- All columns
SELECT * FROM tasks;

-- Specific columns
SELECT id, title, completed FROM tasks;

-- With WHERE clause
SELECT * FROM tasks WHERE priority = 'high';
SELECT * FROM tasks WHERE completed = true;
SELECT * FROM tasks WHERE due_date < CURRENT_DATE;

-- With AND/OR
SELECT * FROM tasks WHERE priority = 'high' AND completed = false;
SELECT * FROM tasks WHERE priority = 'high' OR priority = 'medium';

-- Pattern matching
SELECT * FROM tasks WHERE title ILIKE '%fastapi%';  -- Case-insensitive

-- Sorting
SELECT * FROM tasks ORDER BY created_at DESC;
SELECT * FROM tasks ORDER BY priority, title;

-- Limit/Offset (pagination)
SELECT * FROM tasks LIMIT 10 OFFSET 20;
```

### Update
```sql
UPDATE tasks SET completed = true WHERE id = 5;
UPDATE tasks SET priority = 'high', tags = ARRAY['urgent'] WHERE id = 3;
```

### Delete
```sql
DELETE FROM tasks WHERE id = 5;
DELETE FROM tasks WHERE completed = true;
```

---

## PostgreSQL Specific Features

### SERIAL (Auto-increment)
```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY
);

-- Behind the scenes creates a sequence:
-- tasks_id_seq
-- IDs never reuse, even after deletion
```

### Arrays
```sql
-- Create with array
INSERT INTO tasks (tags) VALUES (ARRAY['backend', 'api']);

-- Query array contains
SELECT * FROM tasks WHERE 'backend' = ANY(tags);
SELECT * FROM tasks WHERE tags @> ARRAY['backend'];
```

### Current Timestamp
```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- Automatically sets to current time when row created
```

---

## SQLAlchemy ORM (Object-Relational Mapping)

### What is an ORM?
Translates between Python objects and database tables.

**Without ORM (raw SQL):**
```python
cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
row = cursor.fetchone()
task = {"id": row[0], "title": row[1], ...}
```

**With ORM (SQLAlchemy):**
```python
task = db.query(Task).filter(Task.id == task_id).first()
print(task.title)
```

### Benefits
- Write Python, not SQL
- Type safety and IDE autocomplete
- Automatic SQL injection protection
- Database-agnostic (easier to switch databases)
- Relationship handling

---

## SQLAlchemy Core Concepts

### Engine (Connection Pool Manager)
```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://user:password@localhost:5432/dbname"
engine = create_engine(DATABASE_URL, echo=True)
```

**What it does:**
- Manages connection pool to database
- Reuses connections efficiently
- `echo=True` prints SQL queries (for learning/debugging)

**Think of it as:** The phone line to the database—create once, reuse everywhere.

---

### SessionLocal (Transaction Factory)
```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

**What it does:**
- Creates database sessions (like opening a transaction)
- `autocommit=False` - changes aren't saved until you call `commit()`
- `autoflush=False` - changes aren't sent to DB until `commit()`

**Session lifecycle:**
```python
db = SessionLocal()      # Start session
db.add(task)             # Stage changes
db.commit()              # Save to database
db.refresh(task)         # Reload from DB (get auto-generated values)
db.close()               # End session
```

**Think of it as:** Opening a conversation with the database, making changes, saving them, hanging up.

---

### Base (Model Foundation)
```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
```

**What it does:**
- All database models inherit from `Base`
- Tracks all model definitions
- `Base.metadata.create_all(engine)` creates tables

**Think of it as:** The parent class that gives models database superpowers.

---

### Dependency Injection (get_db)
```python
def get_db():
    db = SessionLocal()
    try:
        yield db           # Give session to endpoint
    finally:
        db.close()         # Always close, even if error

@router.get("/tasks")
def get_tasks(db: Session = Depends(get_db)):
    # db is automatically provided and cleaned up
    tasks = db.query(Task).all()
    return tasks
```

**How it works:**
1. FastAPI calls `get_db()`
2. Session created and yielded
3. Your endpoint uses the session
4. Endpoint finishes
5. `finally` block runs → session closes

**Think of it as:** Borrowing a car—you get the keys, drive, return it, and it's automatically parked.

---

## SQLAlchemy Models

### Defining a Model
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ARRAY
from sqlalchemy.sql import func

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
```

**Column options:**
- `primary_key=True` - Unique identifier
- `index=True` - Create database index (faster lookups)
- `nullable=False` - Cannot be NULL (required)
- `nullable=True` - Can be NULL (optional)
- `default=value` - Python-side default
- `server_default=func.now()` - Database-side default (SQL function)

**Common types:**
- `Integer` - Whole numbers
- `String(n)` - Text with max length
- `Text` - Unlimited text
- `Boolean` - True/False
- `DateTime` - Timestamp with time
- `Date` - Just the date
- `Float` - Decimal numbers
- `ARRAY(String)` - PostgreSQL array

---

## SQLAlchemy Queries

### Basic Query Pattern
```python
# Build query (doesn't hit database yet)
query = db.query(Task)
query = query.filter(Task.completed == True)
query = query.order_by(Task.created_at.desc())

# Execute query
tasks = query.all()        # Get all results
task = query.first()       # Get first result or None
count = query.count()      # Count results
```

**Important:** Queries are lazy—nothing happens until you call `.all()`, `.first()`, `.count()`, etc.

---

### CRUD Operations

**CREATE:**
```python
task = Task(
    title="New task",
    priority="high",
    tags=["backend"]
)
db.add(task)
db.commit()
db.refresh(task)  # Get the auto-generated ID
```

**READ:**
```python
# Get all
tasks = db.query(Task).all()

# Get one by ID
task = db.query(Task).filter(Task.id == 5).first()

# Filter
tasks = db.query(Task).filter(Task.completed == True).all()
tasks = db.query(Task).filter(Task.priority == "high").all()
```

**UPDATE:**
```python
task = db.query(Task).filter(Task.id == 5).first()
task.title = "Updated title"
task.completed = True
db.commit()
db.refresh(task)
```

**DELETE:**
```python
task = db.query(Task).filter(Task.id == 5).first()
db.delete(task)
db.commit()
```

---

### Filter Operations

**Comparison:**
```python
.filter(Task.id == 5)                    # Equals
.filter(Task.priority != "low")          # Not equals
.filter(Task.id > 10)                    # Greater than
.filter(Task.id >= 10)                   # Greater than or equal
.filter(Task.created_at < date.today())  # Less than
```

**Text search:**
```python
.filter(Task.title.like("%fastapi%"))     # Case-sensitive LIKE
.filter(Task.title.ilike("%fastapi%"))    # Case-insensitive LIKE
```

**NULL checks:**
```python
.filter(Task.due_date.is_(None))          # IS NULL
.filter(Task.due_date.isnot(None))        # IS NOT NULL
```

**Array operations:**
```python
.filter(Task.tags.contains(["backend"]))  # Array contains
.filter(Task.tags.any("backend"))         # Any element matches
```

**IN operator:**
```python
.filter(Task.id.in_([1, 3, 5]))           # WHERE id IN (1, 3, 5)
```

**Boolean operators:**
```python
# AND (two ways)
.filter(Task.completed == True, Task.priority == "high")
.filter((Task.completed == True) & (Task.priority == "high"))

# OR
.filter((Task.priority == "high") | (Task.priority == "medium"))
```

---

### Sorting
```python
.order_by(Task.created_at)              # Ascending (oldest first)
.order_by(Task.created_at.desc())       # Descending (newest first)
.order_by(Task.priority, Task.title)    # Multiple fields
```

---

### Pagination
```python
.offset(20)      # Skip first 20 results
.limit(10)       # Return max 10 results

# Together (page 3, 10 per page):
.offset(20).limit(10)
```

---

### Chaining (Building Complex Queries)
```python
query = db.query(Task)

if completed is not None:
    query = query.filter(Task.completed == completed)

if priority:
    query = query.filter(Task.priority == priority)

if search:
    query = query.filter(Task.title.ilike(f"%{search}%"))

query = query.order_by(Task.created_at.desc())
query = query.offset(skip).limit(limit)

tasks = query.all()  # Execute the built query
```

---

## SQLAlchemy vs Pydantic Models

### You Need Both!

**SQLAlchemy Models (`db_models.py`):**
- Define database tables and columns
- Used for talking to PostgreSQL
- Handle database operations
```python
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
```

**Pydantic Models (`models.py`):**
- Define API request/response structure
- Used for validation and JSON serialization
- Handle API communication
```python
class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    priority: Literal["low", "medium", "high"]
```

### The Flow
```
Client JSON
    ↓
Pydantic validates (TaskCreate)
    ↓
Endpoint function
    ↓
Create SQLAlchemy object (db_models.Task)
    ↓
Save to PostgreSQL
    ↓
Query SQLAlchemy object back
    ↓
FastAPI converts to JSON using Pydantic (Task)
    ↓
Client receives JSON
```

### Making Them Work Together

In Pydantic models, add:
```python
class Task(BaseModel):
    id: int
    title: str
    completed: bool
    
    model_config = ConfigDict(from_attributes=True)  # Important!
```

`from_attributes=True` tells Pydantic: "You can create this from SQLAlchemy objects (which use `.title` instead of `['title']`)."

---

## SQL Injection Protection

### The Problem
```python
# DANGEROUS - never do this!
query = f"SELECT * FROM tasks WHERE title = '{user_input}'"
# If user_input = "'; DROP TABLE tasks; --"
# You just deleted your table!
```

### How SQLAlchemy Protects You
```python
# SAFE - SQLAlchemy uses parameterized queries
db.query(Task).filter(Task.title == user_input)

# Behind the scenes:
# SQL: WHERE title = %(title_1)s
# Parameters: {'title_1': "'; DROP TABLE tasks; --"}
# PostgreSQL treats it as literal string, not SQL code
```

**Key point:** Never use f-strings or string concatenation for SQL. Always use SQLAlchemy's filter methods.

---

## Common Patterns

### Find or 404
```python
task = db.query(Task).filter(Task.id == task_id).first()
if not task:
    raise HTTPException(404, f"Task {task_id} not found")
return task
```

### Update Multiple Fields
```python
task = db.query(Task).filter(Task.id == task_id).first()
update_data = {"title": "New", "completed": True}
for field, value in update_data.items():
    setattr(task, field, value)
db.commit()
```

### Counting
```python
total = db.query(Task).count()
completed = db.query(Task).filter(Task.completed == True).count()
```

### Checking Existence
```python
exists = db.query(Task).filter(Task.id == task_id).first() is not None
# or
exists = db.query(Task.id).filter(Task.id == task_id).first() is not None
```

---

## Alembic (Database Migrations)

### What is Alembic?
Version control for your database schema. Like Git, but for database structure.

### Why Use It?
- Track schema changes over time
- Apply changes without losing data
- Roll back changes if needed
- Share schema changes with team
- Deploy to production safely

---

### Core Concepts

**Migration:**
A file that describes changes to your database schema.

**Revision:**
A unique ID for each migration (forms a chain).

**Upgrade:**
Apply a migration (move forward).

**Downgrade:**
Reverse a migration (move backward).

**Head:**
The latest migration.

---

### Setup (One Time)
```bash
# Install
pip install alembic

# Initialize
alembic init alembic

# Configure alembic.ini
sqlalchemy.url = postgresql://user:pass@localhost:5432/dbname

# Configure alembic/env.py
from db_config import Base
from db_models import Task  # Import all models
target_metadata = Base.metadata

# Mark current state (if tables exist)
alembic stamp head
```

---

### Common Commands

**Generate migration (detects changes):**
```bash
alembic revision --autogenerate -m "Add notes field"
```

**Apply migrations:**
```bash
alembic upgrade head        # Apply all pending
alembic upgrade +1          # Apply one migration
alembic upgrade abc123      # Upgrade to specific revision
```

**Rollback migrations:**
```bash
alembic downgrade -1        # Undo last migration
alembic downgrade abc123    # Downgrade to specific revision
alembic downgrade base      # Undo all migrations
```

**View status:**
```bash
alembic current             # Show current migration
alembic history             # Show all migrations
alembic show abc123         # Show specific migration
```

**Mark as applied (without running):**
```bash
alembic stamp head          # Mark current as applied
alembic stamp abc123        # Mark specific revision
```

---

### How Autogenerate Works

1. **Reads your SQLAlchemy models** (what schema should be)
2. **Reads your database** (what schema currently is)
3. **Compares them** (finds differences)
4. **Generates migration** (SQL to make database match models)
```bash
alembic revision --autogenerate -m "Add notes field"
```

Creates file like: `alembic/versions/abc123_add_notes_field.py`

---

### Migration File Structure
```python
"""Add notes field to tasks

Revision ID: abc123def456
Revises: xyz789abc012       # Previous migration
Create Date: 2025-11-24 14:30:00
"""

from alembic import op
import sqlalchemy as sa

revision = 'abc123def456'    # This migration's ID
down_revision = 'xyz789'     # Previous migration's ID

def upgrade() -> None:
    # Changes to apply
    op.add_column('tasks', sa.Column('notes', sa.String(500)))

def downgrade() -> None:
    # How to reverse the changes
    op.drop_column('tasks', 'notes')
```

---

### Common Operations

**Add column:**
```python
op.add_column('tasks', sa.Column('notes', sa.String(500), nullable=True))
```

**Drop column:**
```python
op.drop_column('tasks', 'notes')
```

**Rename column:**
```python
op.alter_column('tasks', 'notes', new_column_name='comments')
```

**Change column type:**
```python
op.alter_column('tasks', 'priority', type_=sa.String(50))
```

**Create table:**
```python
op.create_table(
    'users',
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('email', sa.String(255), nullable=False)
)
```

**Drop table:**
```python
op.drop_table('users')
```

---

### The Migration Chain
```
None → abc123 → def456 → ghi789 (head)
```

Each migration points to the previous one via `down_revision`.

**alembic_version table:**
Tracks which migration is currently applied.
```sql
SELECT * FROM alembic_version;
-- version_num
-- -----------
-- ghi789
```

---

### Workflow Example

**Scenario:** Add "assignee" field to tasks
```bash
# 1. Update model
# In db_models.py: add assignee = Column(String(100))

# 2. Generate migration
alembic revision --autogenerate -m "Add assignee field"

# 3. Review generated file
# Check alembic/versions/xyz_add_assignee_field.py

# 4. Apply locally
alembic upgrade head

# 5. Test your app
# Make sure everything works

# 6. Commit migration file
git add alembic/versions/xyz_add_assignee_field.py
git commit -m "Add assignee field migration"

# 7. On production:
git pull
alembic upgrade head
```

---

### Autogenerate Limitations

**Can detect:**
- ✅ New tables
- ✅ New columns
- ✅ Removed columns
- ✅ Type changes (usually)

**Cannot detect:**
- ❌ Column renames (sees as drop + add)
- ❌ Table renames (sees as drop + add)
- ❌ Index changes (sometimes)
- ❌ Constraint changes (sometimes)

For these, manually edit the migration file.

---

### Best Practices

1. **Always review generated migrations** before applying
2. **Test migrations on development database first**
3. **Commit migration files to Git** (they're code!)
4. **Never edit applied migrations** (create new ones instead)
5. **Keep migrations small and focused** (one logical change per migration)
6. **Write reversible migrations** (ensure downgrade works)

---

## Transaction Concepts

### What is a Transaction?

A group of database operations that either all succeed or all fail together.

**Example:**
```python
db = SessionLocal()
try:
    task1 = Task(title="Task 1")
    db.add(task1)
    
    task2 = Task(title="Task 2")
    db.add(task2)
    
    db.commit()  # Both saved together
except:
    db.rollback()  # Neither saved
finally:
    db.close()
```

### ACID Properties

- **Atomicity** - All or nothing
- **Consistency** - Database stays valid
- **Isolation** - Transactions don't interfere with each other
- **Durability** - Committed data persists

---

## Performance Considerations

### Indexes
```python
# In model:
id = Column(Integer, primary_key=True, index=True)

# Creates database index for faster lookups
# Good for columns you filter/sort by often
# Trade-off: Faster reads, slower writes
```

### N+1 Query Problem
```python
# BAD - queries database for each task's user
tasks = db.query(Task).all()
for task in tasks:
    print(task.user.name)  # Separate query each time!

# GOOD - join in one query (we'll learn this with relationships)
tasks = db.query(Task).join(User).all()
```

### Only Select What You Need
```python
# If you only need IDs and titles:
db.query(Task.id, Task.title).all()
# vs
db.query(Task).all()  # Fetches all columns
```

---

## Debugging Tips

### See Generated SQL
```python
# In db_config.py:
engine = create_engine(DATABASE_URL, echo=True)
# Prints all SQL queries to terminal
```

### Check What's in Session
```python
print(db.new)        # Objects to be inserted
print(db.dirty)      # Objects to be updated
print(db.deleted)    # Objects to be deleted
```

### Rollback if Stuck
```python
db.rollback()  # Undo uncommitted changes
```

---

## Common Mistakes I Made

### 1. Forgetting to Commit
```python
# WRONG - changes not saved!
task.title = "Updated"
db.close()

# CORRECT
task.title = "Updated"
db.commit()
db.close()
```

### 2. Not Refreshing After Commit
```python
# Create task
task = Task(title="New")
db.add(task)
db.commit()
print(task.id)  # None! ID not loaded yet

# CORRECT
db.refresh(task)
print(task.id)  # 5
```

### 3. Modifying Arrays Without flag_modified
```python
# WRONG - SQLAlchemy doesn't detect change
task.tags.append("urgent")
db.commit()  # Doesn't save!

# CORRECT
from sqlalchemy.orm.attributes import flag_modified
task.tags.append("urgent")
flag_modified(task, "tags")
db.commit()
```

### 4. Reusing IDs
PostgreSQL SERIAL never reuses IDs. Gaps are normal and expected.

### 5. Session Per Request
Always create one session per request, close it when done.
```python
# FastAPI handles this with Depends(get_db)
```

---

## Key Takeaways

### SQLAlchemy Flow
```
1. Create session (SessionLocal())
2. Build query or create object
3. Execute query or add/update/delete
4. Commit changes
5. Close session
```

### Models Are Source of Truth
```
Your SQLAlchemy models → Alembic → Database
(always update models first, then generate migrations)
```

### Safety Features
- Parameterized queries prevent SQL injection
- Transactions ensure data consistency
- Migrations prevent data loss during schema changes

---

## Resources

- [SQLAlchemy Docs](https://docs.sqlalchemy.org/en/20/)
- [PostgreSQL Tutorial](https://www.postgresqltutorial.com/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [FastAPI SQL Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)

---

**Last Updated:** November 24, 2025  
**Current Week:** 3-4 (Databases & Migrations)