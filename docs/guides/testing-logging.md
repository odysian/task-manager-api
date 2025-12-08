# Testing, Error Handling & Logging

A reference for pytest testing patterns, custom exception handling, and production-quality logging in FastAPI applications.

---

## Table of Contents
- [Testing with Pytest](#testing-with-pytest)
- [Custom Exception Handling](#custom-exception-handling)
- [Logging](#logging)
- [Key Learnings](#key-learnings)

---

## Testing with Pytest

### Why Test?
- Catch bugs before they reach production
- Ensure features work as expected
- Prevent regressions when adding new features
- Document how your API should behave
- Give you confidence when refactoring

### Test Database Setup

**Separate test database prevents polluting production data:**

```python
# conftest.py - pytest configuration and fixtures
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_config import Base
from main import app

# Test database connection
TEST_DATABASE_URL = "postgresql://task_user:dev_password@localhost/task_manager_test"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)  # Create tables
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)  # Clean up after test
```

**Key concepts:**
- `scope="function"` - New database for each test (isolated, independent)
- `create_all()` - Create tables before test
- `yield` - Pause and give session to test
- `drop_all()` - Clean up tables after test

### Test Client Setup

**FastAPI's TestClient simulates HTTP requests without running server:**

```python
from fastapi.testclient import TestClient

@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with test database"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**Why override dependencies?**
- Tells FastAPI to use test database instead of production
- Each test gets a clean, isolated database

### Factory Functions for Common Patterns

**Reduce duplication by creating reusable helper functions:**

```python
def create_user_and_token(client, username="testuser", email="test@example.com", password="password123"):
    """Register user and return auth token - used in almost every test"""
    # Register
    client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    
    # Login
    response = client.post("/auth/login", json={
        "username": username,
        "password": password
    })
    
    token = response.json()["access_token"]
    return token

# Usage in tests
def test_create_task(client):
    token = create_user_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post("/tasks", json={"title": "My task"}, headers=headers)
    assert response.status_code == 201
```

**Why factory functions?**
- Every test needs authentication → Don't repeat registration/login code
- Clean, readable tests focused on what you're testing
- Easy to create multiple users for authorization tests

### Writing Tests

**Basic test structure:**

```python
def test_something(client):
    # Arrange - Set up test data
    token = create_user_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Act - Perform the action
    response = client.post("/tasks", json={"title": "Test"}, headers=headers)
    
    # Assert - Check the results
    assert response.status_code == 201
    assert response.json()["title"] == "Test"
```

**Common test patterns:**

```python
# Test successful operation
def test_create_task_success(client):
    token = create_user_and_token(client)
    response = client.post("/tasks", 
        json={"title": "New task", "priority": "high"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New task"
    assert data["priority"] == "high"

# Test failure case
def test_create_task_unauthenticated(client):
    response = client.post("/tasks", json={"title": "Test"})
    assert response.status_code == 401

# Test validation
def test_create_task_invalid_priority(client):
    token = create_user_and_token(client)
    response = client.post("/tasks",
        json={"title": "Test", "priority": "invalid"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422  # Validation error

# Test authorization (multi-user)
def test_user_cannot_access_other_users_task(client):
    # User A creates task
    token_a = create_user_and_token(client, username="usera", email="a@test.com")
    response = client.post("/tasks", 
        json={"title": "User A's task"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    task_id = response.json()["id"]
    
    # User B tries to access it
    token_b = create_user_and_token(client, username="userb", email="b@test.com")
    response = client.get(f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 403  # Forbidden
```

### Running Tests

```bash
# Run all tests
pytest

# Verbose output (shows each test name)
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run specific test function
pytest tests/test_auth.py::test_register_user

# Show print statements (useful for debugging)
pytest -s

# Stop on first failure
pytest -x

# Run tests matching a pattern
pytest -k "test_create"

# Coverage report
pytest --cov=. --cov-report=html
```

### What to Test

**Always test:**
- ✅ Happy path (things work as expected)
- ✅ Authentication/authorization (who can access what)
- ✅ Validation (invalid input is rejected)
- ✅ Not found cases (404 errors)
- ✅ Edge cases (empty lists, missing optional fields)

**Don't need to test:**
- ❌ FastAPI's built-in validation (trust the framework)
- ❌ Third-party libraries (they have their own tests)
- ❌ Database operations (trust SQLAlchemy)

**Focus on testing YOUR business logic:**
- Does user A see only their tasks?
- Does bulk update handle missing IDs correctly?
- Does the stats endpoint calculate correctly?

---

## Custom Exception Handling

### Why Custom Exceptions?

**Problem with HTTPException everywhere:**
```python
# Hard to maintain, duplicated logic, no type safety
if not task:
    raise HTTPException(status_code=404, detail="Task not found")
```

**Solution with custom exceptions:**
```python
# Clear, reusable, type-safe
if not task:
    raise TaskNotFoundError(task_id=task_id)
```

### Creating Custom Exceptions

**Define your exception classes:**

```python
# exceptions.py
class TaskNotFoundError(Exception):
    """Raised when a task doesn't exist"""
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.message = f"Task with ID {task_id} not found"
        super().__init__(self.message)

class UnauthorizedTaskAccessError(Exception):
    """Raised when user tries to access another user's task"""
    def __init__(self, task_id: int, user_id: int):
        self.task_id = task_id
        self.user_id = user_id
        self.message = f"User {user_id} is not authorized to access task {task_id}"
        super().__init__(self.message)

class DuplicateUserError(Exception):
    """Raised when trying to register with existing username/email"""
    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        self.message = f"{field.capitalize()} '{value}' is already registered"
        super().__init__(self.message)

class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid"""
    def __init__(self):
        self.message = "Invalid username or password"
        super().__init__(self.message)

class TagNotFoundError(Exception):
    """Raised when trying to remove a tag that doesn't exist"""
    def __init__(self, task_id: int, tag: str):
        self.task_id = task_id
        self.tag = tag
        self.message = f"Tag '{tag}' not found on task {task_id}"
        super().__init__(self.message)
```

**Key patterns:**
- Store relevant data (task_id, user_id, etc.)
- Create a descriptive message
- Call `super().__init__(self.message)` to set exception message

### Exception Handlers

**Register handlers in main.py to convert exceptions to HTTP responses:**

```python
# main.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import exceptions

app = FastAPI()

@app.exception_handler(exceptions.TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: exceptions.TaskNotFoundError):
    """Handle TaskNotFoundError by returning 404"""
    logger.error(f"TaskNotFoundError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Task Not Found",
            "message": exc.message,
            "task_id": exc.task_id
        }
    )

@app.exception_handler(exceptions.UnauthorizedTaskAccessError)
async def unauthorized_task_handler(request: Request, exc: exceptions.UnauthorizedTaskAccessError):
    """Handle UnauthorizedTaskAccessError by returning 403"""
    logger.warning(f"UnauthorizedTaskAccessError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "Unauthorized Access",
            "message": "You do not have permission to access this task"
            # Don't expose task_id or user_id for security
        }
    )

@app.exception_handler(exceptions.InvalidCredentialsError)
async def invalid_credentials_handler(request: Request, exc: exceptions.InvalidCredentialsError):
    """Handle InvalidCredentialsError by returning 401"""
    logger.warning(f"InvalidCredentialsError: {exc.message} (path: {request.url.path})")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": "Authentication Failed",
            "message": exc.message
        },
        headers={"WWW-Authenticate": "Bearer"}  # Required for 401
    )
```

**Why exception handlers?**
- Centralize error response formatting
- Consistent error structure across entire API
- Separate concerns (business logic vs HTTP responses)
- Easy to add logging in one place

### Using Exceptions in Endpoints

```python
# routers/tasks.py
from exceptions import TaskNotFoundError, UnauthorizedTaskAccessError

@router.get("/{task_id}")
def get_task(task_id: int, current_user: User = Depends(get_current_user), ...):
    task = db_session.query(Task).filter(Task.id == task_id).first()
    
    # Clean, readable error handling
    if not task:
        raise TaskNotFoundError(task_id=task_id)
    
    if task.user_id != current_user.id:
        raise UnauthorizedTaskAccessError(task_id=task_id, user_id=current_user.id)
    
    return task
```

### When to Use Custom Exceptions vs HTTPException

**Use custom exceptions for:**
- ✅ Business logic errors (task not found, unauthorized access)
- ✅ Errors that appear in multiple places
- ✅ When you want structured error data
- ✅ When you want centralized logging

**Use HTTPException for:**
- ✅ Simple validation (no fields provided for update)
- ✅ One-off errors that won't be reused
- ✅ Pydantic already validates most input

**Balance:** Not everything needs a custom exception. Pragmatism over perfection.

---

## Logging

### Why Logging?

**Logging provides:**
- Audit trail (who did what, when)
- Debugging information (what went wrong)
- Security monitoring (failed logins, unauthorized access)
- Performance insights (how many requests, slow operations)

**Without logging, you're flying blind in production.**

### Logging Configuration

**Set up dual output (console + file):**

```python
# logging_config.py
import logging
from pathlib import Path

def setup_logging():
    """Configure logging with console and file output"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,  # Minimum level to log
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            # Console handler
            logging.StreamHandler(),
            # File handler
            logging.FileHandler('logs/app.log', encoding='utf-8')
        ]
    )
    
    logging.info("Logging configured successfully")
```

**Format breakdown:**
- `%(asctime)s` - Timestamp
- `%(name)s` - Logger name (module name)
- `%(levelname)s` - Log level (INFO, WARNING, ERROR)
- `%(message)s` - Your log message

### Log Levels

```python
logger.debug("Detailed debugging info")    # DEBUG - Very detailed, usually off
logger.info("Normal operation")            # INFO - Confirmations things are working
logger.warning("Something suspicious")     # WARNING - Potential issues
logger.error("Something failed")           # ERROR - Actual errors
logger.critical("System is broken")        # CRITICAL - Severe problems
```

**When to use each level:**
- **INFO**: User logged in, task created, successful operations
- **WARNING**: Failed login, unauthorized access attempt, duplicate username
- **ERROR**: Task not found, database error, exceptions
- **DEBUG**: Detailed data (usually disabled in production)

### Using Loggers in Your Code

**Create a logger in each module:**

```python
# routers/auth.py
import logging

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)  # __name__ = "routers.auth"

@router.post("/register")
def register_user(user_data: UserCreate, ...):
    logger.info(f"Registration attempt for username: {user_data.username}, email: {user_data.email}")
    
    # Check if username exists
    existing_user = db_session.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        logger.warning(f"Registration failed: username '{user_data.username}' already exists")
        raise DuplicateUserError(field="username", value=user_data.username)
    
    # Create user...
    logger.info(f"User registered successfully: username='{new_user.username}', user_id={new_user.id}")
    return new_user
```

**Why `logging.getLogger(__name__)`?**
- Each module gets its own logger
- Logger name shows up in logs: `routers.auth - INFO - ...`
- Easy to filter logs by module

### Logging Patterns

**1. Log at operation boundaries:**
```python
@router.post("/tasks")
def create_task(task_data: TaskCreate, current_user: User = Depends(get_current_user), ...):
    # Log at start with key parameters
    logger.info(f"Creating task for user_id={current_user.id}: title='{task_data.title}'")
    
    # Do the work...
    new_task = Task(...)
    db_session.add(new_task)
    db_session.commit()
    
    # Log success at end with results
    logger.info(f"Task created successfully: task_id={new_task.id}, user_id={current_user.id}")
    return new_task
```

**2. Log warnings for business rule violations:**
```python
if task.user_id != current_user.id:
    logger.warning(f"Unauthorized access attempt: user_id={current_user.id} tried to access task_id={task_id}")
    raise UnauthorizedTaskAccessError(...)
```

**3. Log in exception handlers:**
```python
@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: TaskNotFoundError):
    logger.error(f"TaskNotFoundError: {exc.message} (path: {request.url.path})")
    return JSONResponse(...)
```

**4. Always include context:**
```python
# Bad - no context
logger.info("Task created")

# Good - who, what, when
logger.info(f"Task created successfully: task_id={new_task.id}, user_id={current_user.id}")
```

### What to Log

**Always log:**
- ✅ Authentication events (login, registration, failures)
- ✅ Authorization failures (unauthorized access attempts)
- ✅ State changes (create, update, delete operations)
- ✅ Errors and exceptions
- ✅ Application startup/shutdown

**Be selective about:**
- ⚠️ High-frequency operations (GET all tasks - log count, not details)
- ⚠️ Sensitive data (never log passwords, tokens, or full credit cards)

**Good logging example:**
```
2025-11-29 00:10:58 - routers.auth - INFO - Registration attempt for username: chris, email: chris@example.com
2025-11-29 00:10:58 - routers.auth - INFO - User registered successfully: username='chris', user_id=1
2025-11-29 00:10:59 - routers.auth - WARNING - Login failed for username: chris (invalid credentials)
2025-11-29 00:11:03 - routers.tasks - INFO - Creating task for user_id=1: title='Important work'
2025-11-29 00:11:03 - routers.tasks - INFO - Task created successfully: task_id=1, user_id=1
2025-11-29 00:11:03 - routers.tasks - WARNING - Unauthorized access attempt: user_id=2 tried to access task_id=1
```

### Application Lifespan Events

**Log startup and shutdown:**

```python
# main.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Task Manager API starting up")
    yield
    # Shutdown
    logger.info("Task Manager API shutting down")

app = FastAPI(
    title="Task Manager API",
    lifespan=lifespan
)
```

**Why lifespan instead of `@app.on_event()`?**
- `on_event` is deprecated in newer FastAPI versions
- `lifespan` is the modern, recommended approach
- Uses async context manager pattern

### Viewing Logs

```bash
# Watch logs in real-time
tail -f logs/app.log

# Search for specific user's actions
grep "user_id=5" logs/app.log

# Find all errors
grep "ERROR" logs/app.log

# Find security events (warnings)
grep "WARNING" logs/app.log

# Find all login attempts
grep "Login attempt" logs/app.log
```

---

## Key Learnings

### Testing
- **Test database isolation is critical** - Each test needs a clean slate
- **Factory functions reduce duplication** - Don't repeat user creation in every test
- **Test authorization with multiple users** - Create two users, ensure they can't see each other's data
- **Testing finds bugs** - Found issues with completed field and status codes during testing
- **Focus on business logic** - Don't test FastAPI's built-in features

### Error Handling
- **Custom exceptions are cleaner** - Better than HTTPException everywhere
- **Balance is important** - Not everything needs a custom exception
- **Exception handlers centralize formatting** - Consistent error responses across API
- **Don't leak information** - Don't expose user_ids or internal details in error messages
- **Log in exception handlers** - Complete audit trail of what went wrong

### Logging
- **Log at strategic points** - Start, success, warnings, errors
- **Include context** - Always log user_id, task_id, etc.
- **Use appropriate levels** - INFO for normal, WARNING for suspicious, ERROR for failures
- **Logging is your production debugger** - Without logs, you can't troubleshoot production issues
- **Balance verbosity** - Too much logging = noise, too little = blind

### General
- **Multi-user isolation is tricky** - Must check ownership everywhere
- **Good tests give confidence** - Can refactor knowing tests will catch breaks
- **Production-quality != perfect** - Pragmatism over perfection
- **These three topics work together** - Testing validates behavior, errors handle failures gracefully, logging tracks everything

---

## Quick Reference

### Common pytest Commands
```bash
pytest                          # Run all tests
pytest -v                       # Verbose
pytest tests/test_auth.py       # Specific file
pytest -k "test_create"         # Pattern matching
pytest -x                       # Stop on first failure
pytest -s                       # Show print statements
pytest --cov=.                  # Coverage report
```

### Common Logging Patterns
```python
# Create logger
logger = logging.getLogger(__name__)

# Log operation start
logger.info(f"Operation starting: param={value}")

# Log warning
logger.warning(f"Suspicious activity: user_id={user_id}")

# Log error
logger.error(f"Operation failed: {error_msg}")

# Log success
logger.info(f"Operation completed successfully: result={result}")
```

### Exception Pattern
```python
# Define exception
class CustomError(Exception):
    def __init__(self, param):
        self.param = param
        self.message = f"Error: {param}"
        super().__init__(self.message)

# Raise in endpoint
if error_condition:
    raise CustomError(param=value)

# Handle in main.py
@app.exception_handler(CustomError)
async def handler(request: Request, exc: CustomError):
    logger.error(f"CustomError: {exc.message}")
    return JSONResponse(status_code=400, content={"error": exc.message})
```

---

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [FastAPI Exception Handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [HTTP Status Codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)

---

**Last Updated:** November 29, 2025  
**Week:** 7-8 (Testing & Error Handling)  
**Status:** Complete ✅
