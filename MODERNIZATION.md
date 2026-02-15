# MODERNIZATION.md — Task Manager API

Changes needed to bring this project in line with the standards defined in `WORKFLOW.md`. This is a reference for future work — not a mandate. Each section is independent and can be tackled incrementally.

---

## 1. Async Migration

**Current:** Sync SQLAlchemy (`create_engine`, `sessionmaker`, `psycopg2-binary`). Endpoints use `def`.

**Target:** Async throughout (`create_async_engine`, `async_sessionmaker`, `asyncpg`). Endpoints use `async def`.

**Changes required:**
- Replace `psycopg2-binary` with `asyncpg` in requirements.txt
- Rewrite `db_config.py` to use `create_async_engine` and `async_sessionmaker`
- Change `get_db()` to `async def get_db()` yielding `AsyncSession`
- Convert all router endpoints from `def` to `async def`
- Convert all `db_session.query(...)` calls to `await db_session.execute(select(...))`
- Convert all `db_session.commit()` to `await db_session.commit()`
- Update `services/background_tasks.py` to use async sessions
- Update `tests/conftest.py` to use async fixtures (`pytest-asyncio`)

**Risk:** High — touches every file. Recommend doing this as a dedicated migration, not alongside feature work.

---

## 2. SQLAlchemy 2.0 Model Style

**Current:** 1.x-style `Column()` definitions.

```python
# Current
id = Column(Integer, primary_key=True, index=True)
email = Column(String(100), unique=True, nullable=False)
```

**Target:** 2.0-style `Mapped[]` / `mapped_column()`.

```python
# Target
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
```

**Changes required:**
- Rewrite all models in `db_models.py` using `Mapped`, `mapped_column`, `DeclarativeBase`
- Update relationship declarations to use `Mapped[list["Model"]]` syntax
- Generate Alembic migration (should be no-op if column types match)

**Risk:** Medium — model-only change, but every file that imports models needs testing.

---

## 3. SQLAlchemy 2.0 Query Style

**Current:** 1.x `db.query(Model).filter(...)` pattern.

```python
# Current
user = db_session.query(db_models.User).filter(db_models.User.username == username).first()
```

**Target:** 2.0 `select()` + `execute()` pattern.

```python
# Target
stmt = select(User).where(User.username == username)
result = await db_session.execute(stmt)
user = result.scalar_one_or_none()
```

**Changes required:**
- Replace all `db_session.query()` calls across routers, dependencies, services
- Use `select()`, `update()`, `delete()` from sqlalchemy
- Use `selectinload()` for relationship eager loading where needed

**Note:** Best done together with the async migration (#1).

---

## 4. BIGINT Primary Keys

**Current:** `Integer` primary keys on all tables.

**Target:** `BigInteger` primary keys per WORKFLOW.md convention.

**Changes required:**
- Update `db_models.py`: change all PK columns to `BigInteger`
- Create Alembic migration to ALTER COLUMN types
- Update foreign key columns to match (Integer → BigInteger)

**Risk:** Low — straightforward schema change. Test migration carefully on existing data.

---

## 5. Structured `app/` Package

**Current:** Flat root-level layout (`main.py`, `db_models.py`, `db_config.py`, `dependencies.py` at project root).

**Target:** Nested `app/` package per WORKFLOW.md:

```
app/
├── __init__.py
├── main.py
├── config.py          # was db_config.py
├── database.py        # engine, session factory
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── task.py
│   ├── comment.py
│   ├── file.py
│   ├── share.py
│   ├── notification.py
│   └── activity.py
├── schemas/           # move from root
├── routers/           # move from root
├── services/          # move from root
├── dependencies/
│   ├── __init__.py
│   ├── auth.py        # was dependencies.py
│   └── database.py    # get_db
├── middleware/
├── core/              # move from root
└── utils/
```

**Changes required:**
- Create `app/` package with `__init__.py`
- Move all modules inside
- Update all import paths
- Update `alembic/env.py` to import from `app.models`
- Update `uvicorn main:app` to `uvicorn app.main:app`
- Update Dockerfile entrypoint
- Update pytest configuration

**Risk:** High — every import changes. Recommend doing this in one atomic commit.

---

## 6. Split `db_models.py` Into Per-Domain Files

**Current:** Single `db_models.py` with all 7 models.

**Target:** One model file per domain under `app/models/` with `__init__.py` re-exporting all models.

Best done together with #5 (package restructure).

---

## 7. Add Ruff + Mypy

**Current:** `pylint` + `black` for linting/formatting.

**Target:** Replace with `ruff` (linting + formatting) and add `mypy` for type checking.

**Changes required:**
- Add `ruff` and `mypy` to requirements.txt
- Create `pyproject.toml` with ruff configuration
- Create `mypy.ini` or add `[mypy]` section to `pyproject.toml`
- Remove `pylint`, `black`, `.pylintrc`
- Update CI workflow to use `ruff check .` and `mypy . --ignore-missing-imports`
- Update AGENTS.md verification commands
- Fix any new lint/type errors surfaced

---

## 8. Add Bandit

**Current:** No security scanning.

**Target:** `bandit` for automated security checks.

**Changes required:**
- Add `bandit` to requirements.txt
- Add `bandit -r app/ -ll` to CI pipeline
- Fix any findings

---

## 9. httpOnly Cookie Authentication

**Current:** JWT sent as Bearer token in Authorization header. Frontend stores token in `localStorage`.

**Target:** JWT set as httpOnly cookie. Frontend sends credentials automatically.

**Changes required (backend):**
- Login endpoint sets `Set-Cookie: access_token=<jwt>; HttpOnly; Secure; SameSite=Lax`
- `get_current_user` reads token from cookie instead of Authorization header
- Logout endpoint clears the cookie
- CORS config ensures `allow_credentials=True` (already set)

**Changes required (frontend):**
- Remove `localStorage.getItem('token')` / `setItem` logic
- Remove Authorization header interceptor from `api.js`
- Add `credentials: 'include'` to all API calls (already set via axios `withCredentials`)
- Auth state determined by API call (e.g., GET /users/me) not localStorage

**Risk:** Medium — changes auth flow for both repos. Must be coordinated.

---

## 10. TIMESTAMPTZ for All Datetime Columns

**Current:** Mixed — some columns use `DateTime(timezone=True)`, others use bare `DateTime`.

Affected columns (bare `DateTime` without timezone):
- `tasks.created_at` — `DateTime` (no tz)
- `task_files.uploaded_at` — `DateTime` (Python default, no tz)
- `task_comments.updated_at` — `DateTime` (no tz)
- `task_shares.shared_at` — `DateTime` (no tz)

**Target:** All datetime columns use `DateTime(timezone=True)` which maps to PostgreSQL `TIMESTAMPTZ`.

**Changes required:**
- Update affected columns in `db_models.py`
- Create Alembic migration to ALTER COLUMN types
- Test that existing data is preserved correctly

---

## 11. Pydantic-Settings for Configuration

**Current:** Raw `os.getenv()` calls scattered across `db_config.py`, `core/security.py`, `core/redis_config.py`, `core/storage.py`, `core/email.py`.

**Target:** Single `Settings` class using `pydantic-settings`:

```python
from pydantic_settings import BaseSettings, ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REDIS_URL: str = "redis://localhost:6379/0"
    STORAGE_PROVIDER: str = "local"
    EMAIL_PROVIDER: str = "resend"
    # ... etc

settings = Settings()
```

**Changes required:**
- Add `pydantic-settings` to requirements.txt
- Create `app/config.py` with Settings class
- Replace all `os.getenv()` calls with `settings.FIELD`
- Validate all required fields at startup (fail fast)

---

## 12. Test Coverage Gaps

See `TESTPLAN.md` for the full list of uncovered tests. Priority areas:

1. **Task CRUD completeness** — update, delete, filtering, pagination, bulk operations
2. **Sharing permissions** — view vs edit enforcement, cascading deletes
3. **File operations** — upload validation, download, delete, cascade
4. **Notification preferences** — get, update, email verification
5. **User endpoints** — profile, avatar, search, password change edge cases
6. **Activity** — all resource types, filtering, stats

---

## Recommended Order

These changes have dependencies. Recommended sequence:

1. **TIMESTAMPTZ columns** (#10) — Small, safe, standalone
2. **Pydantic-settings** (#11) — Small, improves config
3. **Ruff + Mypy + Bandit** (#7, #8) — Tooling, no code logic changes
4. **Test coverage** (#12) — Safety net before larger refactors
5. **BIGINT PKs** (#4) — Schema change, needs migration
6. **Package restructure** (#5, #6) — Import-only changes
7. **SQLAlchemy 2.0 models** (#2) — Model syntax update
8. **Async + 2.0 queries** (#1, #3) — Largest change, do last
9. **httpOnly cookies** (#9) — Coordinates with frontend, do when ready
