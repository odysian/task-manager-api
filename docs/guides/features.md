# Advanced Features

Reference for background tasks, file uploads, Redis caching, and rate limiting in FastAPI applications.

---

## Background Tasks

### Why Use Background Tasks?

Some operations take time but users don't need to wait:
- Sending emails/notifications
- Cleanup operations
- Logging analytics
- Processing uploaded files

**Without background tasks:**
```python
def create_task():
    task = save_to_db()
    send_email()  # User waits 5 seconds 😴
    return task
```

**With background tasks:**
```python
def create_task(background_tasks: BackgroundTasks):
    task = save_to_db()
    background_tasks.add_task(send_email)  # Runs after response ⚡
    return task  # Returns immediately
```

### Creating Background Task Functions

```python
# background_tasks.py
import logging
logger = logging.getLogger(__name__)

def send_notification(user_email: str, task_title: str):
    """Background task function - just a regular Python function"""
    logger.info(f"BACKGROUND TASK: Sending notification to {user_email}")
    
    # Simulate slow operation (email API call, etc.)
    import time
    time.sleep(2)
    
    logger.info(f"NOTIFICATION SENT: {task_title} to {user_email}")
```

**Rules for background task functions:**
- Just regular Python functions (not async required)
- Can accept parameters
- Should log what they're doing
- Run AFTER response is sent
- No access to request/response (already gone)

### Using Background Tasks in Endpoints

```python
from fastapi import BackgroundTasks
from background_tasks import send_notification

@router.post("/tasks")
def create_task(
    background_tasks: BackgroundTasks,  # Add this dependency
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    ...
):
    # Create task normally
    new_task = Task(...)
    db_session.add(new_task)
    db_session.commit()
    
    # Schedule background task
    background_tasks.add_task(
        send_notification,
        user_email=current_user.email,  # type: ignore
        task_title=new_task.title  # type: ignore
    )
    
    return new_task  # Returns immediately, notification sends later
```

### When to Use Background Tasks

**Good for:**
- ✅ Quick async operations (<30 seconds)
- ✅ Notifications (email, Slack, SMS)
- ✅ Cleanup operations
- ✅ Simple analytics logging

**Not good for:**
- ❌ Long operations (>30 seconds) - use Celery
- ❌ Operations that must succeed - use task queue with retries
- ❌ Jobs that need to survive server restart
- ❌ Distributed tasks across multiple servers

---

## File Uploads

### Concepts

**File upload flow:**
1. Client sends file in multipart/form-data
2. Server validates (size, type, permissions)
3. Save to disk with unique filename
4. Store metadata in database
5. Return file info to client

**Why unique filenames?**
```
User uploads: photo.jpg
Stored as:    task_5_a1b2c3d4-uuid_photo.jpg
```
Prevents conflicts, tracks ownership, easy to clean up.

### Database Model

```python
# db_models.py
class TaskFile(Base):
    __tablename__ = "task_files"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    original_filename = Column(String(255))  # User's filename
    stored_filename = Column(String(255), unique=True)  # Unique on disk
    file_size = Column(Integer)
    content_type = Column(String(100))  # MIME type
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    task = relationship("Task", back_populates="files")

# Update Task model
class Task(Base):
    # ... existing columns ...
    files = relationship("TaskFile", back_populates="task", cascade="all, delete-orphan")
```

**What is `cascade="all, delete-orphan"`?**
When you delete a task, SQLAlchemy automatically deletes its files from the database.

### File Upload Endpoint

```python
import uuid
from pathlib import Path
from fastapi import UploadFile, File

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx", ".txt"}

@router.post("/{task_id}/files")
async def upload_file(  # async for file I/O
    task_id: int,
    file: UploadFile = File(...),
    db_session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify task ownership
    task = db_session.query(Task).filter(Task.id == task_id).first()
    if not task or task.user_id != current_user.id:
        raise exceptions.UnauthorizedTaskAccessError(...)
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()  # type: ignore
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Read and validate size
    content = await file.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())
    stored_filename = f"task_{task_id}_{unique_id}{file_ext}"
    file_path = UPLOAD_DIR / stored_filename
    
    # Save to disk
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Save metadata to database
    task_file = TaskFile(
        task_id=task_id,
        original_filename=file.filename,  # type: ignore
        stored_filename=stored_filename,
        file_size=file_size,
        content_type=file.content_type
    )
    db_session.add(task_file)
    db_session.commit()
    
    return task_file
```

### File Download Endpoint

```python
from fastapi.responses import FileResponse

@router.get("/files/{file_id}")
async def download_file(
    file_id: int,
    db_session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get file record
    task_file = db_session.query(TaskFile).filter(TaskFile.id == file_id).first()
    if not task_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check ownership (using relationship!)
    if task_file.task.user_id != current_user.id:  # type: ignore
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Check file exists on disk
    file_path = UPLOAD_DIR / task_file.stored_filename  # type: ignore
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Return file
    return FileResponse(
        path=file_path,
        filename=task_file.original_filename,  # type: ignore - User sees original name
        media_type=task_file.content_type  # type: ignore
    )
```

### File Deletion with Background Cleanup

```python
# background_tasks.py
def cleanup_files(file_list: list[str]):
    """Delete files from disk"""
    for stored_filename in file_list:
        file_path = UPLOAD_DIR / stored_filename
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"Deleted file: {stored_filename}")

# In delete_task endpoint
@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    ...
):
    task = # ... get and verify task ...
    
    # Get list of files to delete (using relationship!)
    file_list = [file.stored_filename for file in task.files]
    
    # Delete task (CASCADE deletes TaskFile records automatically)
    db_session.delete(task)
    db_session.commit()
    
    # Delete files from disk in background
    background_tasks.add_task(cleanup_files, file_list=file_list)
    
    return None
```

### File Upload Key Points

- Always validate file type and size
- Generate unique filenames (use UUID)
- Check user permissions (ownership)
- Two-step save: disk then database
- Clean up files when task is deleted
- Use relationships to navigate task → files

---

## Redis Caching

### Why Cache?

**Problem:** Expensive operations repeated unnecessarily
```python
GET /tasks/stats  # Query DB, count everything, calculate
GET /tasks/stats  # Same exact query 2 seconds later... 😞
```

**Solution:** Store result in RAM for fast retrieval
```python
GET /tasks/stats  # Calculate, store in Redis (50ms)
GET /tasks/stats  # Get from Redis (0.5ms) - 100x faster! 🚀
```

### Installing Redis

```bash
# Install Redis
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test it works
redis-cli ping  # Should return: PONG

# Install Python client
pip install redis
```

### Redis Configuration

```python
# redis_config.py
import redis
import logging

logger = logging.getLogger(__name__)

# Redis settings
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
STATS_CACHE_TTL = 300  # 5 minutes

# Create Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True  # Automatically convert bytes to strings
)

def get_cache(key: str) -> str | None:
    """Get value from cache, returns None if not found"""
    try:
        value = redis_client.get(key)
        if value:
            logger.info(f"Cache HIT: {key}")
        else:
            logger.info(f"Cache MISS: {key}")
        return value
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return None

def set_cache(key: str, value: str, ttl: int = STATS_CACHE_TTL) -> bool:
    """Set value in cache with expiration"""
    try:
        redis_client.setex(key, ttl, value)  # Set with TTL in one command
        logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return False

def delete_cache(key: str) -> bool:
    """Delete value from cache"""
    try:
        redis_client.delete(key)
        logger.info(f"Cache DELETE: {key}")
        return True
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return False

def invalidate_user_cache(user_id: int):
    """Clear all cache for a user"""
    stats_key = f"stats:user_{user_id}"
    delete_cache(stats_key)
```

### Using Cache in Endpoints

```python
import json
from redis_config import get_cache, set_cache, invalidate_user_cache

@router.get("/stats")
def get_task_stats(
    db_session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Build cache key (unique per user)
    cache_key = f"stats:user_{current_user.id}"
    
    # Try to get from cache
    cached_stats = get_cache(cache_key)
    if cached_stats:
        # Cache hit - return immediately
        return json.loads(cached_stats)
    
    # Cache miss - calculate from database
    all_tasks = db_session.query(Task).filter(
        Task.user_id == current_user.id
    ).all()
    
    # Calculate stats...
    stats_dict = {
        "total": len(all_tasks),
        "completed": sum(1 for t in all_tasks if t.completed),
        # ... more stats ...
    }
    
    # Store in cache for next time
    set_cache(cache_key, json.dumps(stats_dict))
    
    return stats_dict
```

### Cache Invalidation

**When data changes, clear the cache:**

```python
@router.post("/tasks")
def create_task(...):
    # Create task...
    db_session.commit()
    
    # Invalidate cache since stats changed
    invalidate_user_cache(current_user.id)  # type: ignore
    
    return new_task
```

**Add invalidation to:**
- Create task
- Update task
- Delete task
- Bulk update
- Complete task

### Cache Key Strategy

```python
# Per-user cache keys
stats:user_1  # User 1's stats
stats:user_2  # User 2's stats

# Why per-user?
# Each user has different data, so different stats
# Can't share cache between users
```

### Redis Data Types

Redis stores strings, so convert Python objects:

```python
# Store (dict → JSON string)
stats_dict = {"total": 5, "completed": 3}
set_cache("stats:user_1", json.dumps(stats_dict))

# Retrieve (JSON string → dict)
cached = get_cache("stats:user_1")
stats_dict = json.loads(cached)
```

### Redis CLI Commands

```bash
redis-cli

# See all keys
KEYS *

# Get a value
GET "stats:user_1"

# Check TTL (time to live)
TTL "stats:user_1"  # Returns seconds until expiration

# Delete a key
DEL "stats:user_1"

# See all stats
INFO stats
```

### Caching Best Practices

**What to cache:**
- ✅ Expensive calculations
- ✅ Frequently accessed data
- ✅ Data that doesn't change often

**What NOT to cache:**
- ❌ User-specific sensitive data (if shared Redis)
- ❌ Data that changes constantly
- ❌ Small/fast queries (not worth the complexity)

**Cache TTL guidelines:**
- Stats/analytics: 5-15 minutes
- User profiles: 30-60 minutes
- Configuration: 1-24 hours

---

## Rate Limiting

### Why Rate Limit?

**Without rate limiting:**
- Brute force attacks (try 10,000 passwords)
- API spam (create 1 million tasks)
- DDoS attacks (overwhelm server)
- Resource exhaustion (fill disk with uploads)

**With rate limiting:**
- "5 login attempts per minute"
- "100 requests per hour per user"
- Automatic 429 Too Many Requests response

### Installing slowapi

```bash
pip install slowapi
```

### Rate Limiter Configuration

```python
# rate_limit_config.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_user_id_or_ip(request: Request) -> str:
    """
    Get identifier for rate limiting.
    Priority: user_id (if authenticated) > IP address
    """
    if hasattr(request.state, "user"):
        user = request.state.user
        return f"user_{user.id}"
    
    # Fall back to IP
    ip = get_remote_address(request)
    return f"ip_{ip}"

# Create limiter
limiter = Limiter(
    key_func=get_user_id_or_ip,
    default_limits=["1000/hour"],  # Default for all endpoints
    storage_uri="redis://localhost:6379",  # Use Redis to track limits
    strategy="fixed-window"
)
```

### Adding Limiter to FastAPI

```python
# main.py
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limit_config import limiter

app = FastAPI(...)

# Add limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
```

### Applying Rate Limits to Endpoints

```python
from rate_limit_config import limiter
from fastapi import Request

# Strict limit for login (prevent brute force)
@router.post("/login")
@limiter.limit("5/minute")
def login_user(
    request: Request,  # Required by limiter
    login_data: UserLogin,
    ...
):
    # ... login logic ...

# Moderate limit for registration
@router.post("/register")
@limiter.limit("10/hour")
def register_user(
    request: Request,
    user_data: UserCreate,
    ...
):
    # ... registration logic ...

# Lenient limit for reads
@router.get("/tasks")
@limiter.limit("1000/hour")  # Or just use default
def get_tasks(
    request: Request,
    ...
):
    # ... get tasks logic ...
```

### Rate Limit Patterns

```python
# Common patterns
@limiter.limit("5/minute")        # 5 per minute
@limiter.limit("100/hour")        # 100 per hour
@limiter.limit("1000/day")        # 1000 per day

# Multiple limits (most restrictive wins)
@limiter.limit("5/minute;100/hour")

# Custom per endpoint
@limiter.limit("20/hour", path_pattern="/upload")
```

### Recommended Limits by Endpoint Type

**Authentication (strict):**
- Login: `5/minute` - prevent brute force
- Register: `10/hour` - prevent spam accounts

**Write operations (moderate):**
- Create task: `100/hour`
- File upload: `20/hour` - prevent storage abuse
- Bulk update: `50/hour` - expensive operation

**Read operations (lenient):**
- Get tasks: `1000/hour` or default
- Get stats: `1000/hour` (cached anyway)

### Storing User in Request State

Update `dependencies.py` so rate limiter can identify users:

```python
def get_current_user(
    request: Request,  # Add this parameter
    token: str = Depends(oauth2_scheme),
    db_session: Session = Depends(get_db)
) -> User:
    # ... verify token and get user ...
    
    # Store user in request state for rate limiter
    request.state.user = user
    
    return user
```

### Testing Rate Limits

```bash
# Try 6 login attempts quickly (limit is 5/minute)
for i in {1..6}; do
  curl -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "test", "password": "wrong"}'
done

# 6th attempt should return 429 Too Many Requests
```

### Viewing Rate Limits in Redis

```bash
redis-cli

# See all rate limit counters
KEYS *LIMITER*

# Check specific counter
GET "LIMITER/user_1/auth/login"
# Returns: "3" (3 attempts so far)

# Check TTL
TTL "LIMITER/user_1/auth/login"
# Returns: 45 (seconds until reset)
```

### Rate Limiting Key Points

- Use Redis for distributed limiting (works across multiple servers)
- Identify by user_id when authenticated, IP when not
- Different limits for different risk levels
- Returns 429 automatically when exceeded
- Add `Request` parameter to all rate-limited endpoints

---

## Quick Reference

### Background Tasks
```python
# Create function
def my_task(param):
    logger.info(f"Running: {param}")

# Use in endpoint
@router.post("/")
def endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(my_task, param="value")
    return result
```

### File Uploads
```python
# Upload
@router.post("/{id}/files")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    # Validate, save to disk, save to DB

# Download
@router.get("/files/{id}")
async def download(...):
    return FileResponse(path=file_path, filename=original_name)
```

### Redis Caching
```python
# Get from cache
cached = get_cache(f"stats:user_{user_id}")
if cached:
    return json.loads(cached)

# Calculate and cache
result = calculate_stats()
set_cache(f"stats:user_{user_id}", json.dumps(result))

# Invalidate
invalidate_user_cache(user_id)
```

### Rate Limiting
```python
# Apply limit
@router.post("/")
@limiter.limit("5/minute")
def endpoint(request: Request, ...):
    # endpoint logic
```

---

## Common Patterns

### Background Task + File Cleanup
```python
# Get files before deletion
file_list = [f.stored_filename for f in task.files]

# Delete from DB
db_session.delete(task)
db_session.commit()

# Clean up files in background
background_tasks.add_task(cleanup_files, file_list)
```

### Cache + Invalidation
```python
# Read with cache
@router.get("/stats")
def get_stats(...):
    cached = get_cache(f"stats:user_{user_id}")
    if cached:
        return json.loads(cached)
    # Calculate and cache
    result = calculate()
    set_cache(f"stats:user_{user_id}", json.dumps(result))
    return result

# Write with invalidation
@router.post("/tasks")
def create_task(...):
    # Create task
    db_session.commit()
    # Invalidate cache
    invalidate_user_cache(user_id)
    return task
```

### File Upload + Validation
```python
# Validate extension
file_ext = Path(file.filename).suffix.lower()
if file_ext not in ALLOWED_EXTENSIONS:
    raise HTTPException(400, "Invalid type")

# Validate size
content = await file.read()
if len(content) > MAX_SIZE:
    raise HTTPException(400, "Too large")

# Save with unique name
unique_id = str(uuid.uuid4())
stored_name = f"task_{task_id}_{unique_id}{file_ext}"
```

---

## Performance Tips

**Background Tasks:**
- Use for operations >1 second
- Don't block response with slow work
- Log everything for debugging

**File Uploads:**
- Set reasonable size limits (10-50 MB)
- Validate before saving to disk
- Use unique filenames (prevent conflicts)
- Clean up files when task deleted

**Caching:**
- Cache expensive calculations only
- Use appropriate TTL (5-15 minutes for stats)
- Always invalidate when data changes
- Per-user cache keys for isolation

**Rate Limiting:**
- Strict on auth endpoints (5/min)
- Moderate on writes (50-100/hour)
- Lenient on reads (1000/hour)
- Use Redis for distributed limiting

---

**Last Updated:** November 30, 2025  
**Week:** 9-10 (Advanced Features)  
**Status:** Complete ✅
