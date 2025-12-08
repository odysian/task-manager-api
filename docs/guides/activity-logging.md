# Activity Logging

> Comprehensive audit trail system tracking all user actions across the application.

## Overview

The activity logging system provides a complete audit trail of user actions, capturing who did what, when, and what changed. Built using a polymorphic database design pattern that allows tracking multiple resource types (tasks, comments, files) with a single table.

## Architecture

### Database Design

**ActivityLog Model:**
```python
class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # created, updated, deleted, shared, unshared
    resource_type = Column(String(50), nullable=False)  # task, comment, file
    resource_id = Column(Integer, nullable=False)
    details = Column(JSON, nullable=True)  # Flexible metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Key design decisions:**
- **Polymorphic pattern**: `resource_type + resource_id` allows tracking any resource without separate tables
- **JSON column**: Stores action-specific metadata (different for each action type)
- **Four strategic indexes** for query performance:
  - `ix_activity_logs_user_id` - "Show me my activity"
  - `ix_activity_logs_created_at` - Time-based filtering
  - `ix_activity_logs_resource` (composite) - "Task timeline"
  - `ix_activity_logs_action` - Audit queries

**Why polymorphic design?**
- Extensible: Add new resource types without schema changes
- Consistent: Same query patterns for all resources
- Flexible: JSON column accommodates different metadata per action

**Alternative considered:** Separate tables per resource (rejected - too rigid, more complex queries)

## Service Layer Pattern

All activity logging goes through `activity_service.py` - business logic separated from HTTP handlers.

### Core Function
```python
def log_activity(
    db_session: Session,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    details: Optional[dict] = None
) -> ActivityLog:
    """
    Core logging function - all activity goes through here.
    
    CRITICAL: Adds to session but does NOT commit.
    Caller controls transaction boundary.
    """
```

**Transaction safety pattern:**
```python
# Endpoint controls the transaction
new_task = Task(...)
db.add(new_task)
db.flush()  # Get ID without committing

log_activity(...)  # Adds log to session

db.commit()  # Both succeed or both fail
```

**Why not commit in service layer?**
- Allows atomic operations (task + log succeed/fail together)
- Caller can bundle multiple operations
- Rollback safety if anything fails

### Helper Functions

Each action type has a dedicated helper:

**Task Actions:**
- `log_task_created()` - Captures title, priority, completed, tags, due_date
- `log_task_updated()` - Captures old_values, new_values, changed_fields
- `log_task_deleted()` - MUST call BEFORE deleting
- `log_task_shared()` - Captures shared_with user info and permission
- `log_task_unshared()` - Captures unshared user info

**Comment Actions:**
- `log_comment_created/updated/deleted` - Includes task_id, content preview

**File Actions:**
- `log_file_uploaded/deleted` - Includes task_id, filename, size, type

## Integration Patterns

### Pattern 1: CREATE Operations
```python
@router.post("/tasks")
def create_task(...):
    new_task = Task(...)
    db.add(new_task)
    db.flush()  # ← CRITICAL: Get ID before logging
    
    activity_service.log_task_created(db, user_id, new_task)
    db.commit()
```

**Why flush?**
- `new_task.id` is None until flushed
- Activity log needs the ID
- flush() executes INSERT and gets ID back (but doesn't commit)

### Pattern 2: UPDATE Operations
```python
@router.patch("/tasks/{id}")
def update_task(...):
    # Capture OLD values BEFORE changes
    old_values = {field: getattr(task, field) for field in update_data.keys()}
    
    # Apply updates
    for field, value in update_data.items():
        setattr(task, field, value)
    
    # Capture NEW values AFTER changes
    new_values = {field: getattr(task, field) for field in update_data.keys()}
    
    activity_service.log_task_updated(db, user_id, task, old_values, new_values)
    db.commit()
```

**Critical insight:** Must capture state BEFORE and AFTER to track what changed.

**Date serialization gotcha:**
```python
# Python date objects aren't JSON-serializable
due_date = task.due_date  # date(2025, 12, 25)

# Convert to ISO string
due_date_str = due_date.isoformat() if due_date else None  # "2025-12-25"
```

### Pattern 3: DELETE Operations
```python
@router.delete("/tasks/{id}")
def delete_task(...):
    # Log BEFORE deleting - data disappears after delete!
    activity_service.log_task_deleted(db, user_id, task)
    
    db.delete(task)
    db.commit()
```

**CRITICAL ORDER:**
1. ✅ Log while object exists
2. ✅ Delete object
3. ✅ Commit both

**Why this matters:** After `delete()`, you can't access `task.title` anymore.

## Query Endpoints

### GET /activity - User's Activity Feed
```python
@router.get("/activity")
def get_my_activity(
    resource_type: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0
):
    query = db.query(ActivityLog).filter(
        ActivityLog.user_id == current_user.id  # Authorization in query
    )
    
    # Apply optional filters
    if resource_type:
        query = query.filter(ActivityLog.resource_type == resource_type)
    # ... more filters
    
    # Eager load user to prevent N+1
    query = query.options(joinedload(ActivityLog.user))
    
    return query.order_by(desc(ActivityLog.created_at)).offset(offset).limit(limit).all()
```

**Key patterns:**
- **Authorization in query** - users only see their activity
- **Dynamic filtering** - only add filters if parameters provided
- **Eager loading** - prevents N+1 query problem
- **Reverse chronological** - most recent first

### GET /activity/tasks/{id} - Task Timeline
```python
@router.get("/activity/tasks/{task_id}")
def get_task_timeline(task_id: int, ...):
    task = db.query(Task).filter(Task.id == task_id).first()
    
    # Use existing permission helper
    require_task_access(task, current_user, db, TaskPermission.VIEW)
    
    logs = db.query(ActivityLog).options(
        joinedload(ActivityLog.user)
    ).filter(
        ActivityLog.resource_type == "task",
        ActivityLog.resource_id == task_id
    ).order_by(ActivityLog.created_at).all()  # Chronological for timeline
    
    return logs
```

**Key differences from activity feed:**
- **Resource-specific** - all logs for one task
- **Permission check** - reuses existing authorization logic
- **Chronological order** - oldest first (timeline view)
- **Shows all users** - collaborative history

## Performance Optimizations

### N+1 Query Problem

**Without optimization:**
```python
logs = db.query(ActivityLog).limit(50).all()  # Query 1

for log in logs:
    print(log.user.username)  # Queries 2-51 (lazy load)
    
# Result: 51 queries!
```

**With eager loading:**
```python
logs = db.query(ActivityLog).options(
    joinedload(ActivityLog.user)  # JOIN users in same query
).limit(50).all()  # Single query

for log in logs:
    print(log.user.username)  # No query - already loaded
    
# Result: 1 query!
```

**SQL generated:**
```sql
SELECT activity_logs.*, users.*
FROM activity_logs
LEFT JOIN users ON activity_logs.user_id = users.id
LIMIT 50
```

### Indexing Strategy

Four indexes cover common query patterns:

1. **user_id index** - "Show my activity" queries
2. **created_at index** - Date range filtering
3. **Composite (resource_type, resource_id)** - "Task timeline" queries
4. **action index** - Audit queries ("show all deletions")

**Index usage example:**
```sql
-- Uses ix_activity_logs_user_id + ix_activity_logs_created_at
SELECT * FROM activity_logs 
WHERE user_id = 3 
  AND created_at > '2025-12-01'
ORDER BY created_at DESC;

-- Uses ix_activity_logs_resource
SELECT * FROM activity_logs 
WHERE resource_type = 'task' 
  AND resource_id = 42;
```

## Testing Strategy

### Test Categories

**Integration tests** - Verify logging happens automatically:
```python
def test_activity_log_created_on_task_creation(client, token):
    # Create task
    response = client.post("/tasks", json={...}, headers={...})
    
    # Verify log created
    logs = client.get("/activity", headers={...}).json()
    assert logs[0]["action"] == "created"
```

**State tracking tests** - Verify old/new values captured:
```python
def test_update_tracks_old_new_values(client, token):
    # Create with title="Original"
    # Update to title="New"
    
    # Verify log shows both values
    log = client.get("/activity?action=updated", headers={...}).json()[0]
    assert log["details"]["old_values"]["title"] == "Original"
    assert log["details"]["new_values"]["title"] == "New"
```

**Authorization tests** - Users only see their own activity:
```python
def test_users_only_see_own_activity(client):
    alice_token = create_user("alice")
    bob_token = create_user("bob")
    
    # Alice creates task
    client.post("/tasks", ..., headers={"Authorization": f"Bearer {alice_token}"})
    
    # Bob's activity should be empty
    bob_logs = client.get("/activity", headers={"Authorization": f"Bearer {bob_token}"}).json()
    assert len(bob_logs) == 0
```

**Permission tests** - Task timelines respect permissions:
```python
def test_task_timeline_requires_permission(client):
    # Alice creates task
    # Bob tries to view timeline → 403
    # Alice shares with Bob
    # Bob tries again → 200
```

## Common Pitfalls & Solutions

### Pitfall 1: Logging After Delete
```python
# ❌ WRONG - task data gone!
db.delete(task)
log_task_deleted(db, user_id, task)  # Can't access task.title anymore

# ✅ RIGHT - capture before deleting
log_task_deleted(db, user_id, task)
db.delete(task)
```

### Pitfall 2: Forgetting to Flush on Create
```python
# ❌ WRONG - task.id is None
new_task = Task(...)
db.add(new_task)
log_task_created(db, user_id, new_task)  # resource_id will be None!

# ✅ RIGHT - flush to get ID
new_task = Task(...)
db.add(new_task)
db.flush()  # Get ID before logging
log_task_created(db, user_id, new_task)
```

### Pitfall 3: Date Serialization
```python
# ❌ WRONG - date objects aren't JSON-serializable
details = {"due_date": task.due_date}  # TypeError at commit time

# ✅ RIGHT - convert to ISO string
details = {
    "due_date": task.due_date.isoformat() if task.due_date else None
}
```

### Pitfall 4: N+1 Queries
```python
# ❌ WRONG - lazy loading causes N queries
logs = db.query(ActivityLog).all()
for log in logs:
    print(log.user.username)  # Query per log!

# ✅ RIGHT - eager load relationships
logs = db.query(ActivityLog).options(
    joinedload(ActivityLog.user)
).all()
for log in logs:
    print(log.user.username)  # No additional queries
```

## Lessons Learned

**Service layer pattern is powerful:**
- Keeps business logic separate from HTTP handlers
- Easy to test (no HTTP mocking needed)
- Reusable across different endpoints

**Transaction boundaries matter:**
- Service functions add to session but don't commit
- Caller controls when transaction completes
- Enables atomic multi-step operations

**Order of operations is critical:**
- Flush before logging creates (need IDs)
- Capture state before updates (need old values)
- Log before deletes (data disappears)

**Performance comes from design:**
- Proper indexing strategy
- Eager loading relationships
- Single query beats many queries

**Polymorphic patterns are flexible:**
- One table tracks multiple resource types
- Easy to add new resource types
- Consistent query patterns

## Future Enhancements

Potential improvements considered:
- **Soft deletes** - Keep deleted resources for audit (rejected for simplicity)
- **Event sourcing** - Rebuild state from event log (over-engineering)
- **Data retention policies** - Archive old logs (future consideration)
- **Real-time updates** - WebSocket notifications (Project #2 candidate)

## Resources

- [SQLAlchemy Polymorphic Pattern](https://docs.sqlalchemy.org/en/20/orm/inheritance.html)
- [PostgreSQL JSON Functions](https://www.postgresql.org/docs/current/functions-json.html)
- [N+1 Query Problem Explained](https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem)