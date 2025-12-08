# RBAC & Task Sharing

Reference for implementing Many-to-Many relationships, Role-Based Access Control, and mocking external services in tests.

-----

## Data Modeling: Many-to-Many Relationships

### The Junction Table

A "One-to-Many" relationship (One User has Many Tasks) uses a simple Foreign Key.
A "Many-to-Many" relationship (One Task shared with Many Users) requires a **Junction Table**.

```python
# db_models.py
class TaskShare(Base):
    __tablename__ = "task_shares"

    # Composite Primary Key concept
    id = Column(Integer, primary_key=True)
    
    # The two sides of the relationship
    task_id = Column(Integer, ForeignKey("tasks.id"))
    shared_with_user_id = Column(Integer, ForeignKey("users.id"))
    
    # Metadata about the relationship
    permission = Column(String)  # "view" or "edit"
    
    # Unique Constraint: Prevent sharing the same task with the same user twice
    __table_args__ = (
        UniqueConstraint('task_id', 'shared_with_user_id', name='unique_task_share'),
    )
```

### SQLAlchemy Relationships

When linking to the same table twice (User sharing vs. User receiving), you must specify `foreign_keys`.

```python
class TaskShare(Base):
    # Receiver
    shared_with = relationship("User", foreign_keys=[shared_with_user_id])
    # Sender
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])
```

-----

## Authorization: RBAC Logic

### The "Permission" Hierarchy

Instead of checking "Is this user the owner?", we check "Does this user have at least level X access?".

```python
class TaskPermission(Enum):
    NONE = "none"
    VIEW = "view"   # Can read
    EDIT = "edit"   # Can update/upload
    OWNER = "owner" # Can delete/share
```

### The "Guard" Pattern

We replaced manual checks (`if task.user_id != user.id`) with a centralized dependency function.

**The Helper (`dependencies.py`):**

```python
def require_task_access(task, user, session, min_permission):
    # 1. Check if Owner (Highest access)
    if task.user_id == user.id:
        return
        
    # 2. Check TaskShare table
    share = session.query(TaskShare).filter(...).first()
    
    # 3. Compare levels
    if permission_levels[user_perm] < permission_levels[min_permission]:
        raise UnauthorizedTaskAccessError(...)
```

**Usage in Endpoints:**

```python
# Read-only operation
require_task_access(task, user, db, TaskPermission.VIEW)

# Destructive operation
require_task_access(task, user, db, TaskPermission.OWNER)
```

-----

## API Design Choices

### Resource Separation

We separated the concepts of "My Tasks" vs "Shared Tasks" to keep the API clean.

  * **`GET /tasks`**: Returns tasks **owned** by the user.
  * **`GET /tasks/shared-with-me`**: Returns tasks **shared** with the user.

### Sub-Resource Permissions

Permissions on the Parent (Task) cascade to the Children (Files/Comments).

  * **Files:**
      * Upload/Delete: Requires **EDIT** on parent task.
      * Download/List: Requires **VIEW** on parent task.
  * **Comments:**
      * View/Create: Requires **VIEW** on parent task.
      * Edit/Delete: Requires **Strict Authorship** (only the comment author can edit the text).

-----

## Testing with Mocks

### Why Mock?

When testing file uploads/downloads, we don't want to actually connect to AWS S3 because:

1.  **Speed:** Real network calls are slow.
2.  **Cost:** AWS charges for storage/requests.
3.  **Isolation:** Tests should not depend on internet connection.

### The "Spy" Pattern

We use `unittest.mock.patch` to intercept calls to `boto3`.

**The Fixture:**

```python
@pytest.fixture
def mock_s3():
    # Path must match where s3_client is DEFINED, not where it is imported
    with patch("routers.files.s3_client") as mock:
        yield mock
```

**The Logic Test (Security):**

```python
def test_viewer_cannot_upload(client, mock_s3):
    # Act: Try to upload as a viewer
    response = client.post(...)
    
    # Assert: We were blocked (403)
    assert response.status_code == 403
    
    # Assert: The code NEVER touched AWS (Security Guard worked)
    mock_s3.put_object.assert_not_called()
```

**The Return Value Test (Download):**

```python
def test_download_file(client, mock_s3):
    # Setup: Create a fake S3 response object
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"fake content"
    
    # Tell the spy what to return when called
    mock_s3.get_object.return_value = {"Body": mock_stream}
    
    # Act
    response = client.get(...)
    
    # Assert
    assert response.content == b"fake content"
```

-----

## Common Pitfalls & Gotchas

### 1 Pydantic Recursion Error

**Problem:** We tried to use an `@property` on the SQLAlchemy model to inject `shared_with_username` into the Pydantic response. This caused an infinite recursion loop.
**Solution:** Removed the property and manually constructed the dictionary in the endpoint return statement.

```python
return {
    "id": share.id,
    "shared_with_username": share.shared_with.username, # Access relationship directly
    ...
}
```

### 2 RequestClient File Uploads

**Problem:** Trying to send files using `client.post(..., file=...)` fails.
**Solution:** The parameter name is **`files=`**, but the dictionary key inside must match the FastAPI endpoint argument name.

```python
# FastAPI: def upload(file: UploadFile)
# Test:
client.post(..., files={"file": ("filename.txt", b"data", "type")})
```

### 3 Dynamic IDs in Tests

**Problem:** Hardcoding IDs (e.g., `user_id=2`) causes tests to break randomly or when run in parallel.
**Solution:** Always extract IDs from previous steps in the test.

```python
# Arrange
task = client.post("/tasks", ...).json()
task_id = task["id"]  # Capture dynamic ID

# Act
client.delete(f"/tasks/{task_id}") # Use variable
```

-----

## Refactoring Checklist

When moving from "Single User" to "Multi User Shared":

1.  [ ] Create Junction Table (`TaskShare`).
2.  [ ] Define Permission Enums (`VIEW`, `EDIT`, `OWNER`).
3.  [ ] Replace `if user_id != current_user` with `require_task_access`.
4.  [ ] Update `DELETE` endpoints to strict `OWNER` only.
5.  [ ] Update `UPDATE` endpoints to `EDIT` access.
6.  [ ] Ensure Bulk operations verify permissions for *every* item in the list.