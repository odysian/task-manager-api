# Event-Driven Notifications & Infrastructure

Reference guide for implementing event-driven architectures, AWS SNS integration, and managing infrastructure side-effects with Terraform and Pytest.

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Service Layer Patterns](#service-layer-patterns)
- [Background Task Isolation](#background-task-isolation)
- [Infrastructure as Code (IaC)](#infrastructure-as-code-iac)
- [Testing Strategy](#testing-strategy)
- [Debugging Workflows](#debugging-workflows)

---

## Architecture Overview

### Event-Driven Architecture (EDA)
Instead of executing notification logic synchronously within the HTTP request cycle, the system decouples the **Action** (e.g., User shares task) from the **Effect** (e.g., Send email).

* **Synchronous:** API request validates input, updates database, returns `200 OK` immediately.
* **Asynchronous:** A background worker picks up the task logic after the response is sent.

**Benefits:**
* **Performance:** Client does not wait for external API calls (AWS SNS).
* **Reliability:** Notification failures do not rollback the primary transaction.

### The Guard Pattern
To prevent spam and enforce privacy, the system implements a series of "Gates" that must be passed before a message is dispatched.

1.  **Verification Gate:** Is `user.email_verified` true?
2.  **Master Switch Gate:** Is `user.email_enabled` true?
3.  **Granular Preference Gate:** Is the specific setting (e.g., `task_shared_with_me`) true?
4.  **Infrastructure Gate:** Is `SNS_TOPIC_ARN` configured in the environment?

---

## Service Layer Patterns

### Logic Separation (`notifications.py`)
Business logic is separated from the API Router. The Router handles HTTP concerns, while the Service Layer handles business rules and external integrations.

* **`should_notify(user_id, type, db)`**: Pure business logic. Determines *if* a notification should be sent based on DB state.
* **`send_notification(...)`**: Infrastructure logic. Handles the raw `boto3` calls to AWS SNS.

### Message Templating
Notification content is centralized in formatter functions rather than hardcoded in routers.

```python
def format_task_shared_notification(title, username, permission):
    return f"Subject", f"Message body with {title}..."
```

-----

## Background Task Isolation

### Request Scope vs. Background Scope

A critical distinction exists between the database session used during a request and the one needed for background tasks.

  * **Request Scope:** Managed by FastAPI (`Depends(get_db)`). Session closes automatically when the response is sent.
  * **Background Scope:** Runs after the response. Attempting to use the request's DB session here will fail because the connection is already closed.

### The Manual Session Pattern

Background tasks must strictly manage their own database lifecycle.

```python
# background_tasks.py
from db_config import SessionLocal

def background_worker(task_id: int):
    # 1. Open a fresh connection specifically for this task
    db = SessionLocal()
    
    try:
        # 2. Perform database operations
        user = db.query(User).get(task_id)
        # ... logic ...
    finally:
        # 3. CRITICAL: Explicitly close the connection
        db.close()
```

-----

## Infrastructure as Code (IaC)

### Automating Resource Wiring

Instead of manually copying ARNs between the AWS Console and local config, Terraform connects resources dynamically.

1.  **Creation:** `sns.tf` defines the topic resource.
2.  **Output:** The ARN is exposed via an output block.
    ```hcl
    output "sns_topic_arn" {
      value = aws_sns_topic.notifications.arn
    }
    ```
3.  **Injection:** `ec2.tf` reads the resource attribute directly and passes it to the User Data script.
    ```hcl
    # ec2.tf
    sns_topic_arn = aws_sns_topic.notifications.arn
    ```

### The "Taint" Workflow

Updating a `user_data` script in Terraform does not automatically update existing EC2 instances, as User Data only runs on first boot.

To force an update:

1.  **Mark as Tainted:** Tell Terraform the instance is "damaged".
    ```bash
    terraform taint aws_instance.api
    ```
2.  **Apply:** Terraform destroys the old instance and provisions a new one, triggering the updated User Data script.
    ```bash
    terraform apply
    ```

### Secrets Management

  * **Local:** `.env` file (gitignored).
  * **Production:** Injected via `user_data.sh.tpl` directly into `/app/.env` on the server.
  * **CI/CD:** Injected via GitHub Actions Secrets.

-----

## Testing Strategy

### Mocking External Services

To test logic without incurring AWS costs or requiring network access, `unittest.mock` is used to "spy" on the `boto3` client.

```python
# tests/test_notifications.py
@pytest.fixture
def mock_sns():
    # Patch the client where it is USED, not where it is defined
    with patch("notifications.sns_client") as mock:
        # Configure return values to prevent crashes
        mock.publish.return_value = {"MessageId": "123"}
        yield mock

def test_notification_sent(client, mock_sns):
    client.post("/share", ...)
    # Assert that code attempted to call AWS
    mock_sns.publish.assert_called_once()
```

### The Database Isolation Fix (`autouse`)

Background tasks importing `SessionLocal` directly from the global scope can bypass test fixtures, causing tests to hit the **Development** database instead of the **Test** database.

**The Solution:** A global patch in `conftest.py` that intercepts all `SessionLocal` calls.

```python
# tests/conftest.py
@pytest.fixture(scope="function", autouse=True)
def patch_background_tasks_db(db_session):
    """
    Redirects all background task DB connections to the 
    current test session.
    """
    def test_session_factory():
        return TestSessionLocal()

    with patch("background_tasks.SessionLocal", side_effect=test_session_factory):
        yield
```

-----

## Debugging Workflows

### 1\. Notification Failures

If a user reports not receiving an email:

  * **Check Logs:**
      * `SNS_TOPIC_ARN not configured`: Infrastructure missing env var.
      * `User X blocked notification`: Application logic (Guard pattern) blocked it.
      * `ClientError`: AWS IAM permissions issue.
  * **Check Database:**
      * Is `email_verified` = true?
      * Is `email_enabled` = true?
  * **Check AWS Console:**
      * Has the user clicked "Confirm Subscription" in their email inbox? (AWS requirement).

### 2\. Infrastructure Drift

If the application environment variables do not match Terraform configuration:

  * **Verify User Data:** Check `/var/log/user-data.log` on the EC2 instance.
  * **Force Update:** Use the `taint` / `apply` workflow to rebuild the instance.

### 3\. CI/CD Failures

If tests fail in GitHub Actions but pass locally:

  * **Check Secrets:** Ensure `SNS_TOPIC_ARN` is set in the `test.yml` environment (can be a dummy value like `arn:aws:sns:us-east-1:123:test`).
  * **Check Database Config:** Ensure background tasks are not trying to connect to `localhost` using production/dev credentials (fixed via `patch_background_tasks_db`).

-----

## Key Commands Reference

**Testing**

```bash
# Run tests with logs visible
pytest -s

# Run specific notification tests
pytest tests/test_notifications.py
```

**Terraform**

```bash
# Preview changes
terraform plan

# Mark instance for recreation
terraform taint aws_instance.api

# Apply infrastructure changes
terraform apply
```

**Database (Local)**

```bash
# Check user preferences
psql -h localhost -U task_user -d task_manager -c "SELECT * FROM notification_preferences;"
```
