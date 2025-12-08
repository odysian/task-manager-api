# Task Manager API

A REST API built with FastAPI, PostgreSQL, and Redis. This is my first major Python web application, built over the course of an accelerated 16-week learning roadmap. I'm learning backend development skills to add onto my Linux, AWS, and Terraform knowledge.

---

## What I Built

A full-featured task management API with:
- Complete CRUD operations with advanced filtering and search
- User authentication with JWT tokens
- Multi-user support with task sharing and granular permissions
- File attachments (upload images/documents to tasks via S3)
- **Activity logging and audit trails** (tracks all user actions)
- Comments system on tasks
- Background tasks (async notifications and cleanup)
- Redis caching 
- Rate limiting 
- **69 passing tests** with pytest
- Production-quality logging
- Automated CI/CD pipeline with zero-downtime deployments

---

## Tech Stack

- **Backend:** FastAPI, Python 3.12
- **Database:** PostgreSQL with SQLAlchemy ORM
- **Caching:** Redis
- **Storage:** AWS S3 (file uploads)
- **Notifications:** AWS SNS (email notifications)
- **Auth:** JWT tokens, bcrypt password hashing
- **Testing:** pytest with test database isolation
- **Deployment:** Docker, GitHub Actions, GitHub Container Registry
- **Infrastructure:** AWS (EC2, RDS, ElastiCache, S3, SNS), Terraform
- **Environment:** Xubuntu VM

---

## Features

**Tasks:**
- Create, read, update, delete tasks
- Filter by completion, priority, tags, overdue status
- Search across title and description
- Sort by any field, paginate results
- Bulk update multiple tasks at once
- Task statistics (completion rate, priority breakdown, tag counts)

**Tags:**
- Add/remove tags from tasks
- Filter tasks by tag

**Files:**
- Upload files to tasks (images, PDFs, documents) to AWS S3
- Download files with proper permission checks
- Delete files
- Automatic cleanup when task is deleted

**Comments:**
- Add comments to tasks
- Update/delete your own comments
- View all comments on tasks you have access to
- Comment authors can always edit their own comments

**Collaboration:**
- Share tasks with other users via username
- RBAC System: Granular permission levels (`VIEW`, `EDIT`, `OWNER`)
- File uploads and comments respect shared permission level
- Viewers can download files but not delete them

**Activity Logging:** *(New!)*
- Comprehensive audit trail of all user actions
- Tracks task creation, updates, deletion, sharing
- Captures old/new values for update operations
- Logs comment and file activity
- Query by action type, resource type, or date range
- Task timeline view shows complete history
- Activity statistics by action and resource type

**Notifications:**
- Event-driven transactional emails via AWS SNS
- Triggers on task sharing, completion, and comments
- Granular user preferences (opt-in/opt-out per event type)
- Global "Do Not Disturb" mode
- Email verification workflow

**Authentication:**
- Register new accounts
- Login with JWT tokens
- All endpoints protected (except registration/login)
- Users can only access their own data

**Performance:**
- Redis caching on stats endpoint (5x faster)
- Background tasks for slow operations
- Rate limiting to prevent abuse
- Eager loading to prevent N+1 queries

**CI/CD:**
- Automated testing on pull requests
- Zero-downtime deployments with blue-green strategy
- Docker image caching (20 second builds)
- Automatic rollback on deployment failure

---

![API Documentation Screenshot](notes/screenshot.png)

## API Endpoints

### Authentication
```
POST /auth/register  - Create account
POST /auth/login     - Get JWT token
```

### Tasks
```
GET    /tasks                 - List all tasks (with filters/search/pagination)
POST   /tasks                 - Create task
GET    /tasks/stats           - Get statistics (cached in Redis)
PATCH  /tasks/bulk            - Update multiple tasks
GET    /tasks/{id}            - Get single task
PATCH  /tasks/{id}            - Update task
DELETE /tasks/{id}            - Delete task
POST   /tasks/{id}/tags       - Add tags
DELETE /tasks/{id}/tags/{tag} - Remove tag
```

### Sharing
```
POST   /tasks/{id}/share              - Share task with user
GET    /tasks/shared-with-me          - List tasks shared with you
PUT    /tasks/{id}/share/{username}   - Update permission (View <-> Edit)
DELETE /tasks/{id}/share/{username}   - Revoke access (Unshare)
```

### Comments
```
POST   /tasks/{task_id}/comments     - Add comment
GET    /tasks/{task_id}/comments     - List comments by task id
PATCH  /tasks/{task_id}/comments/{comment_id}  - Update comment
DELETE /tasks/{task_id}/comments/{comment_id}  - Delete comment
```

### Files
```
POST   /tasks/{id}/files   - Upload file to S3
GET    /tasks/{id}/files   - List files
GET    /files/{id}         - Download file
DELETE /files/{id}         - Delete file
```

### Activity Logs *(New!)*
```
GET    /activity                - Get your activity history (with filters)
GET    /activity/tasks/{id}     - Get complete timeline for a task
GET    /activity/stats          - Get activity statistics
```

### Notifications
```
GET    /notifications/preferences   - Get user preferences
PATCH  /notifications/preferences   - Update preferences
POST   /notifications/subscribe     - Subscribe email to SNS
POST   /notifications/verify        - Verify email address
```

### Health
```
GET    /health   - Check API status and database connection
GET    /version  - Returns version and environment
```

---

## What I Learned

**FastAPI Basics**
- REST API design and HTTP methods
- Request/response validation with Pydantic
- Query parameters and path parameters
- Status codes and error responses

**Database Integration**
- SQLAlchemy ORM (models, sessions, queries)
- Database migrations with Alembic
- Polymorphic database design (activity logs track multiple resource types)
- JSON columns for flexible metadata storage
- Strategic indexing for query performance

**Authentication & Authorization**
- JWT token generation and validation
- Password hashing
- Protected routes with dependencies
- Multi-user data isolation
- RBAC with permission hierarchies (`OWNER` > `EDIT` > `VIEW`)

**Testing & Error Handling**
- pytest with test database isolation
- **69 comprehensive tests** covering all features
- Custom exception classes
- Centralized error handling
- Production logging (helped fix several bugs)
- Mocking external services (S3, SNS) for faster tests

**Advanced Features**
- Background tasks (async operations that don't block responses)
- File uploads with validation and S3 storage
- Redis caching (noticeable performance improvement)
- Rate limiting (prevent brute force and spam)
- SQLAlchemy relationships and eager loading

**Activity Logging** *(What I learned building this feature)*
- Service layer pattern for separating business logic
- Capturing state before/after for audit trails
- **Transaction safety** - logging must happen before commit
- **Critical ordering** - must log deletions before deleting (to capture data)
- Polymorphic patterns for flexible data models
- Date serialization for JSON storage (`.isoformat()`)
- Query optimization with `joinedload()` to prevent N+1 queries

**CI/CD & Deployment**
- GitHub Actions for automated testing and deployment
- Docker layer caching (3min → 20sec builds)
- Blue-green deployment for zero downtime
- Secrets management with GitHub Secrets
- Container registries for image versioning

**Infrastructure as Code**
- Reinforced Terraform concepts from previous AWS project
- More practice with user_data scripts

**Code Quality**
- Linting with pylint, black, and isort
- Consistent code formatting
- Professional code standards (achieved 10/10 pylint score)

---

## Key Learnings

**Testing revealed bugs:**
- `completed` field wasn't respecting input
- Wrong status codes (401 vs 403)
- Registration returning incorrect status

**Multi-user isolation:**
- Every query needs to filter by user_id
- Every single-resource endpoint needs ownership check

**Relationships make database queries much easier:**
- `task.files` gives you all files automatically
- `file.task.user_id` lets you traverse relationships
- Was a bit confusing at first

**Caching is simple but effective:**
- Cache MISS: 1.7ms | Cache HIT: 0.35ms
- Invalidate cache when data changes
- Noticeable impact on read-heavy endpoints

**Background tasks:**
- Don't make users wait for slow operations
- Great for notifications, cleanup, analytics
- Just add `BackgroundTasks` dependency

**Blue-green deployment:**
- Old version keeps serving while new version starts
- Health checks verify new version works before switching
- Automatic rollback if new version fails
- Zero downtime for users

**RBAC is complex but useful:**
- Simple ownership checks break down when you add sharing
- Centralized permission "guards" (`require_task_access`) prevent duplicated logic
- Permissions must cascade to children (if I can't edit the task, I shouldn't delete its files)

**Mocking is essential for cloud testing:**
- Testing S3 file permissions locally is hard/tedious
- Used `unittest.mock` to "spy" on boto3
- Proved that read-only users *never even attempt* to call AWS

**Activity logging patterns:**
- Must flush database to get IDs before logging
- Must capture old values BEFORE applying updates
- Must log deletions BEFORE deleting (data disappears otherwise)
- Service layer keeps business logic separate from HTTP handlers
- Transaction safety ensures logs and changes commit together (or both roll back)

**N+1 query problem:**
- Accessing relationships in loops creates hidden queries
- Use `joinedload()` to fetch related data upfront
- One query is better than 100 queries
- Made a noticeable difference in activity endpoint performance

**Date serialization:**
- Python date objects aren't JSON-serializable
- Convert to ISO format strings with `.isoformat()`
- Important for storing dates in JSON columns

---

## Development Setup
```bash
# Clone repo
git clone https://github.com/odysian/task-manager-api
cd task-manager-api

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up databases (PostgreSQL)
createdb task_manager
createdb task_manager_test

# Set up Redis
sudo apt install redis-server
sudo systemctl start redis-server

# Create .env file with secrets
# Use .env.example as template

# Run migrations
alembic upgrade head

# Start server
uvicorn main:app --reload
```

Visit http://localhost:8000/docs for interactive API documentation.

---

## Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_activity.py
```

**Test coverage:** 69 tests covering auth, CRUD operations, validation, query parameters, stats, bulk operations, tags, sharing, permissions, comments, files, activity logging, and notifications.

---

## Project Structure
```
task-manager-api/
├── main.py                    # App setup, exception handlers
├── models.py                  # Pydantic models (request/response)
├── db_models.py               # SQLAlchemy models (database tables)
├── db_config.py               # Database connection
├── redis_config.py            # Redis caching
├── rate_limit_config.py       # Rate limiting
├── auth.py                    # Password hashing, JWT
├── dependencies.py            # Authentication dependency
├── exceptions.py              # Custom exceptions
├── logging_config.py          # Logging setup
├── background_tasks.py        # Background task functions
├── activity_service.py        # Activity logging service layer
├── routers/
│   ├── auth.py               # Registration, login
│   ├── tasks.py              # Task endpoints
│   ├── sharing.py            # Task sharing endpoints
│   ├── comments.py           # Comment endpoints
│   ├── files.py              # File upload/download
│   ├── activity.py           # Activity log endpoints
│   ├── notifications.py      # Notification preferences
│   └── health.py             # Health check
├── tests/                    # 69 pytest tests
├── uploads/                  # Uploaded files (not in Git)
├── logs/                     # Application logs (not in Git)
├── terraform/                # Infrastructure as Code
└── alembic/                  # Database migrations
```

---

## Current Status

**Just Completed:** Activity Logging & Audit Trails

**What's Working:**
- Complete activity history for all user actions
- Task timelines showing all changes over time
- Activity statistics and filtering
- 69 passing tests with comprehensive coverage
- Automated testing on every pull request
- Zero-downtime deployments on merge to main
- Docker builds with layer caching (20 sec)
- Blue-green deployment with automatic rollback
- Production API live on AWS
- Code quality: 10/10 pylint score

**What's Next:**
- Polish and finalize documentation
- Move to Project #2 (different domain, apply learned patterns)

---

## Deployment

### Architecture
```
                             / RDS PostgreSQL
Internet -> EC2 (Docker) -> │  ElastiCache Redis  
                             \ S3 (file storage)
                               SNS (notifications)
                             
GitHub -> Actions -> GHCR -> EC2 (pull & deploy)
```

### CI/CD Pipeline

**On Pull Request:**
- GitHub Actions spins up PostgreSQL and Redis
- Runs 69 pytest tests
- Reports pass/fail status on PR

**On Merge to Main:**
1. Build job: Creates Docker image with layer caching, pushes to GitHub Container Registry
2. Deploy job: SSHs to EC2, pulls image, runs migrations, blue-green deployment
3. Total time: ~30-60 seconds, downtime: ~2 seconds

**Blue-Green Process:**
- New container starts on port 8001
- Health checks verify it's working (30 attempts)
- If healthy: switches to port 8000
- If unhealthy: automatic rollback

**Production URL:** http://35.173.172.18:8000/docs (Note: AWS instance may be paused to minimize costs.)

### Local Development with Docker
```bash
# Start all services (PostgreSQL, Redis, API)
docker-compose up

# Run in background
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f api
```

Access API at: http://localhost:8000/docs

### Infrastructure as Code (Terraform)

**13 AWS resources** deployed with one command:
- EC2 with IAM role for S3 access (no hardcoded credentials)
- RDS PostgreSQL + ElastiCache Redis
- 3 Security Groups with proper isolation
- Elastic IP for static addressing
- Automated bootstrap via user data script
```bash
cd terraform
terraform init
terraform plan
terraform apply  # ~10-15 minutes
```

**What the bootstrap script does:**
- Installs Docker
- Clones repo from GitHub
- Waits for RDS to be ready
- Creates database (idempotent)
- Runs migrations
- Starts application container

---

## Database Schema

**Key tables:**
- `users` - User accounts and auth
- `tasks` - Task data with owner relationship
- `task_shares` - Many-to-many sharing with permissions
- `task_comments` - Comments on tasks
- `task_files` - File metadata (stored in S3)
- `activity_logs` - Complete audit trail of all actions
- `notification_preferences` - User notification settings

The `activity_logs` table uses a **polymorphic pattern**: `resource_type` + `resource_id` allows tracking any resource (tasks, comments, files) without separate tables.

---

## Resources That Helped Me

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Redis Documentation](https://redis.io/docs/)
- [Real Python](https://realpython.com/)

---

## Contact

**Chris** 
- GitHub: [@odysian](https://github.com/odysian)
- Currently learning: Backend development, building portfolio projects
- Next: Starting Project #2 to reinforce these patterns in a different domain

---

*This project represents the first 3 weeks of my 16-week backend engineering roadmap. Built to demonstrate backend fundamentals for junior backend developer roles.*