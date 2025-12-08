# Authentication & Authorization

Personal reference guide for JWT authentication, password security, and multi-user systems.

---

## Authentication vs Authorization

### Core Concepts

**Authentication** - Proving who you are
- "I am Chris" (username + password)
- Like showing ID at a hotel check-in
- Answers: "Who is this user?"

**Authorization** - What you're allowed to do
- "Chris can only access Chris's tasks"
- Like a hotel key that only opens your room
- Answers: "What can this user do?"

### Real-World Analogy
```
Authentication = Airport security (prove you're the ticket holder)
Authorization = Boarding pass (determines which plane you can board)
```

---

## Password Security

### The Golden Rule
**NEVER store passwords in plain text!**

### The Problem
```python
# DANGEROUS - Never do this!
user.password = "mypassword123"  # Stored as-is in database

# If database is compromised:
# - Attacker sees all passwords
# - Attacker tries same password on email, bank, etc.
# - Users are compromised everywhere
```

### The Solution: Hashing

**Hashing is one-way encryption:**
- Plain password → Hash function → Scrambled string
- Cannot be reversed or decrypted
- Same password always produces same hash
- Tiny change in password = completely different hash

```python
"mypassword123" → hash → "$2b$12$LQv3c1yqC..."
"mypassword124" → hash → "$2b$12$Xk9mP8vR2..."  # Completely different!
```

---

## Bcrypt & Passlib

### What is Bcrypt?

Industry-standard password hashing algorithm.

**Features:**
- Computationally expensive (slow = harder to crack)
- Built-in salt (prevents rainbow table attacks)
- Adjustable cost factor (can make slower as computers get faster)

**Salt:** Random data added to password before hashing
```
Password: "mypassword123"
Salt: random_string_abc123
Hashed: bcrypt("mypassword123" + "abc123") = "$2b$12$..."

# Same password, different salt = different hash
# Prevents attackers from pre-computing hashes
```

### Installation
```bash
pip install "passlib[bcrypt]"
```

### Basic Usage

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash a password
hashed = pwd_context.hash("mypassword123")
# Returns: "$2b$12$LQv3c1yqC4sVPJ..." (60 chars)

# Verify a password
is_correct = pwd_context.verify("mypassword123", hashed)
# Returns: True

is_correct = pwd_context.verify("wrongpassword", hashed)
# Returns: False
```

### Important Notes

- **Hashing is slow by design** (prevents brute force attacks)
- Each hash takes ~100-300ms (this is good!)
- Never compare hashes directly (`hash1 == hash2` won't work due to salts)
- Always use `.verify()` method

---

## JWT (JSON Web Tokens)

### What is a JWT?

A **self-contained token** that proves who you are.

**Structure:** Three parts separated by dots
```
header.payload.signature
eyJhbGc...  .  eyJzdWI...  .  abc123...
```

**Example:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjaHJpcyIsImV4cCI6MTYyMzQ1Njc4OX0.abc123def456
```

### The Three Parts

**1. Header** (base64 encoded JSON)
```json
{
  "alg": "HS256",      // Algorithm used
  "typ": "JWT"         // Token type
}
```

**2. Payload** (base64 encoded JSON)
```json
{
  "sub": "chris",              // Subject (username)
  "exp": 1732543200            // Expiration timestamp
}
```

**3. Signature** (cryptographic seal)
```
HMACSHA256(
  base64(header) + "." + base64(payload),
  SECRET_KEY
)
```

### Key Insight: The Signature

- Anyone can **read** a JWT (it's just base64, not encrypted)
- Only someone with **SECRET_KEY** can **create** or **verify** a JWT
- If payload is tampered with, signature won't match
- Signature proves: "This token was created by our server"

```python
# Token contains: {"sub": "chris"}
# Attacker changes to: {"sub": "admin"}
# Signature no longer matches → Token rejected!
```

---

## JWT Tokens in Practice

### Installation
```bash
pip install "python-jose[cryptography]"
```

### Creating Tokens

```python
# Generate random secret
import secrets
print(secrets.token_urlsafe(32))
```

```python
from jose import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = "your-secret-key-here"  # From environment variable
ALGORITHM = "HS256"

def create_access_token(data: dict) -> str:
    """Create a JWT token with expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Usage:
token = create_access_token({"sub": "chris"})
# Returns: "eyJhbGc..."
```

### Verifying Tokens

```python
from jose import JWTError, jwt

def verify_access_token(token: str) -> dict | None:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # {"sub": "chris", "exp": 1732543200}
    except JWTError:
        return None  # Invalid or expired token

# Usage:
payload = verify_access_token(token)
if payload:
    username = payload.get("sub")
    print(f"Authenticated as: {username}")
else:
    print("Invalid token!")
```

### Token Expiration

**Why tokens expire:**
- If token is stolen, attacker has limited time to use it
- Short TTL = smaller security window
- Forces re-authentication periodically

**Common TTL values:**
- 15-60 minutes: High security (banking apps)
- 1-24 hours: Moderate security (most apps)
- 7-30 days: Convenience over security (social media)

**The trade-off:**
- Short TTL = More secure, but users log in often (annoying)
- Long TTL = More convenient, but stolen token is valid longer (risky)

---

## Stateless Authentication

### How It Works

**Traditional (Stateful) Sessions:**
```
1. User logs in
2. Server creates session, stores in database/Redis
3. Server gives user a session ID
4. Each request: user sends session ID
5. Server looks up session in database
```

**JWT (Stateless) Tokens:**
```
1. User logs in
2. Server creates JWT with user info
3. Server gives user the JWT
4. Each request: user sends JWT
5. Server verifies signature (no database lookup!)
```

### Benefits of Stateless

✅ **Scalable** - No session storage needed, any server can verify  
✅ **Simple** - No Redis/Memcached setup required  
✅ **Fast** - No database lookup on every request  

### Trade-offs

❌ **Can't revoke** - Once issued, token is valid until expiration  
❌ **Size** - JWTs are larger than session IDs  
❌ **No logout** - Client deletes token, but it's still technically valid  

### The Logout "Problem"

**Client-side logout:**
```python
# Client deletes token from storage
localStorage.removeItem('token')
# But the token itself is still valid if someone has a copy!
```

**Why this is usually okay:**
- Tokens expire quickly (15-60 min)
- Users trust their devices
- For most apps, this is acceptable risk

**If you need true revocation:**
- Maintain token blacklist in database (defeats stateless benefits)
- Use short TTL + refresh tokens
- Track active tokens per user

---

## Environment Variables & Security

### The Problem: Hardcoded Secrets

```python
# NEVER DO THIS!
SECRET_KEY = "abc123supersecret"  # Visible in Git history
DATABASE_URL = "postgresql://user:password@localhost/db"
```

**What happens:**
- Secrets visible in source code
- Committed to Git (visible to everyone)
- Hard to change (need to update code and redeploy)
- Different secrets for dev/staging/prod is difficult

### The Solution: Environment Variables

**Local development:** `.env` file (not committed to Git)
**Production:** Environment variables or secrets manager

### Setup

**Install python-dotenv:**
```bash
pip install python-dotenv
```

**Create `.env` file:**
```bash
SECRET_KEY=xK9mP3vR8qL5nW2tY7jH4gF6dS1aZ0bN
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
```

**Add to `.gitignore`:**
```
.env
venv/
__pycache__/
*.pyc
```

**Load in Python:**
```python
from dotenv import load_dotenv
import os

load_dotenv()  # Reads .env file

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
```

### Generating Strong SECRET_KEY

```python
import secrets
print(secrets.token_urlsafe(32))
# Outputs: "xK9mP3vR8qL5nW2tY7jH4gF6dS1aZ0bN"
```

**Requirements for SECRET_KEY:**
- Random (not a dictionary word or pattern)
- Long (32+ characters)
- Never reuse across projects
- Never commit to Git

---

## User Models

### SQLAlchemy Model (Database Table)

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship: one user has many tasks
    tasks = relationship("Task", back_populates="owner")
```

**Key points:**
- `unique=True` on username and email (no duplicates)
- `index=True` for faster lookups (you'll search by username often)
- Field called `hashed_password` (not `password`) - makes intent clear
- `relationship()` allows `user.tasks` to access all tasks

### Pydantic Models (API Validation)

```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    """Request model for registration."""
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=100)
    password: str = Field(min_length=8, max_length=100)

class UserResponse(BaseModel):
    """Response model (what API returns)."""
    id: int
    username: str
    email: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    # Note: NO password field! Never return passwords.

class UserLogin(BaseModel):
    """Request model for login."""
    username: str
    password: str

class Token(BaseModel):
    """Response model for login."""
    access_token: str
    token_type: str  # Always "bearer"
```

**Important patterns:**
- `UserCreate` has `password` (plain text sent by user)
- `UserResponse` has NO password field (never return it)
- Validation rules (min/max length) prevent bad data

---

## Foreign Keys & Relationships

### Adding User Ownership to Tasks

**Update Task model:**
```python
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    # ... other fields ...
    
    # NEW: Link to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="tasks")
```

**What this does:**
- `user_id` column stores which user owns the task
- `ForeignKey` ensures referential integrity (user must exist)
- `relationship` allows Python object access: `task.owner.username`

### Accessing Relationships

```python
# Get user's tasks
user = db.query(User).filter(User.username == "chris").first()
print(user.tasks)  # [Task1, Task2, Task3]

# Get task's owner
task = db.query(Task).filter(Task.id == 5).first()
print(task.owner.username)  # "chris"
```

---

## Authentication Endpoints

### Registration Endpoint

```python
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db_session: Session = Depends(get_db)):
    """Register a new user account."""
    
    # Check if username already exists
    existing_user = db_session.query(db_models.User).filter(
        db_models.User.username == user_data.username
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = db_session.query(db_models.User).filter(
        db_models.User.email == user_data.email
    ).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password
    hashed_password = hash_password(user_data.password)
    
    # Create new user
    new_user = db_models.User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    
    return new_user  # FastAPI converts to UserResponse (no password!)
```

**Flow:**
1. Validate input (Pydantic does automatically)
2. Check username not taken
3. Check email not taken
4. Hash password
5. Store user in database
6. Return user info (without password)

### Login Endpoint

```python
@router.post("/login", response_model=Token)
def login_user(login_data: UserLogin, db_session: Session = Depends(get_db)):
    """Login with username and password."""
    
    # Look up user by username
    user = db_session.query(db_models.User).filter(
        db_models.User.username == login_data.username
    ).first()
    
    # Check if user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
```

**Flow:**
1. Look up user by username
2. If user doesn't exist → vague error
3. Verify password hash matches
4. If password wrong → vague error (same as user not found)
5. Create JWT token with username
6. Return token

**Security note:** Error message is intentionally vague ("Invalid username or password") so attackers can't enumerate valid usernames.

---

## Route Protection with Dependencies

### The Authentication Dependency

FastAPI's **dependency injection** lets us reuse authentication logic.

**Create `dependencies.py`:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from db_config import get_db
import db_models
from auth import verify_access_token

# Tells FastAPI to expect "Authorization: Bearer <token>" header
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_session: Session = Depends(get_db)
) -> db_models.User:
    """
    Dependency that extracts and verifies JWT token from request.
    Returns the authenticated User object.
    """
    # Extract token from Authorization header
    token = credentials.credentials
    
    # Verify and decode token
    payload = verify_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract username from token payload
    username: str | None = payload.get("sub")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Look up user in database
    user = db_session.query(db_models.User).filter(
        db_models.User.username == username
    ).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user
```

### How It Works

**Request flow:**
```
1. Client sends: GET /tasks
   Header: Authorization: Bearer eyJhbGc...

2. FastAPI calls get_current_user()
   ↓
3. HTTPBearer extracts token from header
   ↓
4. verify_access_token() checks signature
   ↓
5. Look up user in database
   ↓
6. Return User object to endpoint
   ↓
7. Endpoint executes with current_user available
```

**If any step fails:**
```
HTTPException(401) raised → Endpoint never executes → Error returned to client
```

### Using the Dependency

**Protected endpoint:**
```python
@router.get("/tasks", response_model=list[Task])
def get_all_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)  # ← Authentication!
):
    """Get all tasks for authenticated user."""
    # current_user is automatically populated if token is valid
    tasks = db_session.query(db_models.Task).filter(
        db_models.Task.user_id == current_user.id  # type: ignore
    ).all()
    return tasks
```

**What FastAPI does:**
1. Calls `get_current_user()` before endpoint
2. If succeeds → passes User object to endpoint
3. If fails → returns 401, endpoint never runs

---

## Multi-User Data Isolation

### The Pattern: Filter by User ID

**Every query must filter by current user:**

```python
# WRONG - returns ALL tasks (security issue!)
tasks = db_session.query(db_models.Task).all()

# CORRECT - returns only current user's tasks
tasks = db_session.query(db_models.Task).filter(
    db_models.Task.user_id == current_user.id  # type: ignore
).all()
```

### Create Operations

**Assign user_id when creating:**
```python
@router.post("/tasks", response_model=Task)
def create_task(
    task_data: TaskCreate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    new_task = db_models.Task(
        title=task_data.title,
        # ... other fields ...
        user_id=current_user.id  # ← Set owner
    )
    db_session.add(new_task)
    db_session.commit()
    return new_task
```

**Important:** User can't specify their own `user_id` (security risk). We set it from the authenticated token.

### Read Operations

**List all tasks (filtered by user):**
```python
@router.get("/tasks", response_model=list[Task])
def get_all_tasks(
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    tasks = db_session.query(db_models.Task).filter(
        db_models.Task.user_id == current_user.id  # type: ignore
    ).all()
    return tasks
```

**Get single task (with ownership check):**
```python
@router.get("/tasks/{task_id}", response_model=Task)
def get_task(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Check ownership
    if task.user_id != current_user.id:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this task"
        )
    
    return task
```

**Why 403 instead of 404?**
- **404** = "This resource doesn't exist"
- **403** = "This resource exists, but you can't access it"

Some APIs use 404 for both (don't leak info about what exists). Either is valid.

### Update Operations

**Same pattern - check ownership first:**
```python
@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Check ownership
    if task.user_id != current_user.id:  # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Update task
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    db_session.commit()
    return task
```

### Delete Operations

**Same pattern:**
```python
@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    task = db_session.query(db_models.Task).filter(
        db_models.Task.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Check ownership
    if task.user_id != current_user.id:  # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    db_session.delete(task)
    db_session.commit()
    return None
```

### Bulk Operations

**Filter by user AND task IDs:**
```python
@router.patch("/bulk", response_model=list[Task])
def bulk_update_tasks(
    bulk_data: BulkTaskUpdate,
    db_session: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    # Query with BOTH filters
    tasks = db_session.query(db_models.Task).filter(
        db_models.Task.user_id == current_user.id,  # type: ignore
        db_models.Task.id.in_(bulk_data.task_ids)
    ).all()
    
    # Only returns tasks that: (1) belong to user AND (2) are in the ID list
    # User can't bulk-update someone else's tasks
    
    # ... rest of update logic
```

**Multiple filters:**
```python
.filter(condition1, condition2)  # Comma = AND
.filter((cond1) & (cond2))       # & operator = AND
.filter((cond1) | (cond2))       # | operator = OR
```

---

## HTTP Status Codes

### Authentication Status Codes

**200 OK** - Successful request (GET with results, empty list is still 200)
```python
return tasks  # Even if empty list, returns 200
```

**201 Created** - Resource created (POST registration)
```python
@router.post("/register", status_code=status.HTTP_201_CREATED)
```

**204 No Content** - Success with no response body (DELETE)
```python
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
return None  # Must return None or omit return
```

**400 Bad Request** - Invalid data (username taken, validation failed)
```python
raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
```

**401 Unauthorized** - Missing or invalid authentication
```python
# Token missing, invalid, or expired
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    headers={"WWW-Authenticate": "Bearer"}
)
```

**403 Forbidden** - Authenticated but not authorized for this resource
```python
# Token valid, but trying to access someone else's data
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
```

**404 Not Found** - Resource doesn't exist
```python
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
```

### Using Named Constants

```python
from fastapi import status

# Instead of:
status_code=201
status_code=404

# Use:
status_code=status.HTTP_201_CREATED
status_code=status.HTTP_404_NOT_FOUND
```

**Benefits:**
- Self-documenting (readable intent)
- Less error-prone (no typos like 440 instead of 404)
- Easier to search codebase

---

## Security Best Practices

### 1. Never Trust Client Input

**Validate everything with Pydantic:**
```python
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)  # Enforce minimum length
```

**Don't let users set their own user_id:**
```python
# BAD - user could set user_id to someone else's ID!
new_task = Task(**task_data.dict())  

# GOOD - always set user_id from authenticated token
new_task = Task(**task_data.dict(), user_id=current_user.id)
```

### 2. Use Strong Passwords

**Enforce requirements:**
- Minimum 8 characters (12+ is better)
- Consider additional checks (uppercase, numbers, symbols)
- Use `Field(min_length=...)` in Pydantic models

### 3. Store Secrets Securely

**Environment variables for secrets:**
```python
# ✅ GOOD
SECRET_KEY = os.getenv("SECRET_KEY")

# ❌ BAD
SECRET_KEY = "abc123"  # Hardcoded
```

**Generate random SECRET_KEY:**
```python
import secrets
secrets.token_urlsafe(32)  # 32+ characters
```

### 4. HTTPS in Production

**All authentication must use HTTPS:**
- Passwords sent over HTTP are visible to attackers
- Tokens sent over HTTP can be stolen
- Always use HTTPS in production

**In development:**
- HTTP localhost is fine (not exposed to internet)

### 5. Vague Error Messages

**Don't leak information:**
```python
# ❌ BAD - tells attacker username exists
"Username not found"
"Password incorrect"

# ✅ GOOD - vague, doesn't leak info
"Invalid username or password"
```

### 6. Short Token Expiration

**Balance security vs convenience:**
```python
# High security
ACCESS_TOKEN_EXPIRE_MINUTES=15

# Moderate security (good for learning/portfolio)
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Low security (only for low-risk apps)
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours
```

### 7. Input Validation

**SQLAlchemy protects from SQL injection:**
```python
# ✅ SAFE - parameterized query
.filter(Task.title == user_input)

# ❌ DANGEROUS - never do this
db.execute(f"SELECT * FROM tasks WHERE title = '{user_input}'")
```

**But still validate input:**
```python
username: str = Field(min_length=3, max_length=50)
# Prevents: empty strings, excessively long input, etc.
```

---

## Common Patterns

### Find User by Username
```python
user = db_session.query(User).filter(User.username == username).first()
if not user:
    raise HTTPException(status_code=404)
```

### Check User Exists
```python
existing = db_session.query(User).filter(User.username == username).first()
if existing:
    raise HTTPException(status_code=400, detail="Username taken")
```

### Verify Password
```python
if not verify_password(plain_password, user.hashed_password):  # type: ignore
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

### Create Token
```python
token = create_access_token({"sub": user.username})
return {"access_token": token, "token_type": "bearer"}
```

### Extract Token Data
```python
payload = verify_access_token(token)
if payload:
    username = payload.get("sub")
```

### Check Task Ownership
```python
if task.user_id != current_user.id:  # type: ignore
    raise HTTPException(status_code=403, detail="Not authorized")
```

---

## Testing Authentication

### Using FastAPI /docs

**1. Register a user:**
- POST /auth/register
- Provide username, email, password

**2. Login:**
- POST /auth/login
- Provide username, password
- Copy the `access_token` from response

**3. Authorize:**
- Click green "Authorize" button (top right)
- Paste token (just the token, not "Bearer token")
- Click "Authorize"
- Click "Close"

**4. Make authenticated requests:**
- All endpoints now include your token automatically
- Lock icon 🔒 shows authentication is required

### Using curl

**Register:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "chris", "email": "chris@test.com", "password": "test1234"}'
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "chris", "password": "test1234"}'
```

**Authenticated request:**
```bash
curl -X GET http://localhost:8000/tasks \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Common Mistakes I Made

### 1. Storing Plain Passwords
```python
# ❌ WRONG
user.password = "mypassword123"

# ✅ CORRECT
user.hashed_password = hash_password("mypassword123")
```

### 2. Returning Passwords in API
```python
# ❌ WRONG - UserResponse includes password
class UserResponse(BaseModel):
    username: str
    password: str  # Never do this!

# ✅ CORRECT - UserResponse excludes password
class UserResponse(BaseModel):
    username: str
    # No password field!
```

### 3. Forgetting to Filter by User
```python
# ❌ WRONG - returns ALL tasks (every user's tasks!)
tasks = db_session.query(Task).all()

# ✅ CORRECT - returns only current user's tasks
tasks = db_session.query(Task).filter(
    Task.user_id == current_user.id  # type: ignore
).all()
```

### 4. Committing .env to Git
```bash
# ❌ Make sure .env is in .gitignore!
git add .env  # NEVER do this!

# ✅ Add to .gitignore
echo ".env" >> .gitignore
```

### 5. Weak SECRET_KEY
```python
# ❌ WRONG
SECRET_KEY = "secret"
SECRET_KEY = "12345"

# ✅ CORRECT - random, long, unique
SECRET_KEY = secrets.token_urlsafe(32)
```

### 6. Not Checking Token Expiration
```python
# The library handles this, but if you manually decode:
payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
# This automatically checks expiration and raises JWTError if expired
```

### 7. Using == to Compare Hashes
```python
# ❌ WRONG - won't work due to salt
if user.hashed_password == hash_password(password):

# ✅ CORRECT - use verify function
if verify_password(password, user.hashed_password):  # type: ignore
```

---

## Advanced: Refresh Tokens

### The Problem

**Short access tokens = good security:**
- Stolen token only works for 15-60 minutes
- BUT: User has to log in every hour (annoying!)

### The Solution: Refresh Tokens

**Two-token system:**

**Access Token:**
- Short-lived (15-60 min)
- Used for API requests
- Stored in memory (not localStorage)

**Refresh Token:**
- Long-lived (7-30 days)
- ONLY used to get new access tokens
- Can be revoked in database
- Stored securely (httpOnly cookie)

### How It Works

```
1. Login → Get access token + refresh token
2. Make requests with access token
3. Access token expires after 15 min
4. App automatically calls /refresh with refresh token
5. Get new access token
6. Continue making requests
7. User never notices expiration (seamless!)
```

### Implementation (Simplified)

```python
# Store refresh tokens in database
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    expires_at = Column(DateTime)

# Login endpoint returns both tokens
@router.post("/login")
def login():
    # ... verify credentials ...
    access_token = create_access_token({"sub": username}, expires_minutes=15)
    refresh_token = create_refresh_token({"sub": username}, expires_days=30)
    
    # Store refresh token in database
    save_refresh_token(refresh_token, user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# Refresh endpoint
@router.post("/refresh")
def refresh(refresh_token: str):
    # Verify refresh token
    payload = verify_refresh_token(refresh_token)
    
    # Check token exists in database and not revoked
    if not token_exists_in_db(refresh_token):
        raise HTTPException(401, "Invalid refresh token")
    
    # Create new access token
    access_token = create_access_token({"sub": payload["sub"]}, expires_minutes=15)
    
    return {"access_token": access_token, "token_type": "bearer"}

# Logout endpoint
@router.post("/logout")
def logout(refresh_token: str):
    # Delete refresh token from database
    delete_refresh_token(refresh_token)
    return {"message": "Logged out successfully"}
```

**For your learning project:** Start with just access tokens. Add refresh tokens later if you want the practice.

---

## Migration: Adding Authentication to Existing App

### The Workflow We Used

**1. Create User model (both SQLAlchemy and Pydantic)**
```python
# db_models.py - add User class
# models.py - add UserCreate, UserResponse, UserLogin, Token
```

**2. Add user_id to Task model**
```python
user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
owner = relationship("User", back_populates="tasks")
```

**3. Create migration**
```bash
# Delete existing tasks (dev environment only!)
DELETE FROM tasks;

# Generate migration
alembic revision --autogenerate -m "Add users and user_id to tasks"

# Apply migration
alembic upgrade head
```

**4. Create auth utilities**
```python
# auth.py - password hashing and JWT functions
# dependencies.py - get_current_user dependency
```

**5. Build auth endpoints**
```python
# routers/auth.py - registration and login
```

**6. Protect existing endpoints**
```python
# Add current_user parameter to all endpoints
# Filter queries by user_id
# Check ownership before updates/deletes
```

**7. Test multi-user isolation**
```
# Create two users
# Verify each can only see their own data
```

---

## Key Takeaways

### Authentication Flow
```
1. User registers → Password hashed → User stored
2. User logs in → Password verified → JWT created
3. User makes request → Token verified → User identified
4. Endpoint executes → Data filtered by user
```

### Security Principles
- Never store plain passwords (always hash)
- Never return passwords in API responses
- Use environment variables for secrets
- Validate all input
- Filter all queries by user_id
- Use HTTPS in production

### FastAPI Patterns
- Pydantic for validation
- Dependencies for reusable logic (get_db, get_current_user)
- HTTPException for errors
- Type hints everywhere

### Multi-User Pattern
```python
# Every endpoint needs:
current_user: User = Depends(get_current_user)

# Every query needs:
.filter(Model.user_id == current_user.id)

# Every create needs:
new_item = Model(..., user_id=current_user.id)
```

---

## Resources

- [FastAPI Security](https://fastapi.tiangelo.com/tutorial/security/)
- [JWT.io](https://jwt.io/) - Decode/debug JWTs
- [Passlib Docs](https://passlib.readthedocs.io/)
- [Python-JOSE Docs](https://python-jose.readthedocs.io/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

---

**Last Updated:** November 25, 2025  
**Current Week:** 5-6 (Authentication & Authorization)  
**Status:** ✅ Complete - JWT authentication working, multi-user system implemented
