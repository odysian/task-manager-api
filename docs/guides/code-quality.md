# Code Quality Standards

> Linting, formatting, and code quality practices for maintaining professional-grade code.

## Overview

This project maintains high code quality standards through automated tooling and consistent practices. Achieved **10/10 pylint score** through systematic improvements.

## Tools

### Black - Code Formatter

**Purpose:** Automatic code formatting to PEP 8 standards
```bash
# Format all Python files
black .

# Check without modifying
black --check .

# Format specific file
black routers/tasks.py
```

**What it fixes:**
- Line length (max 88 characters by default)
- Indentation consistency
- Spacing around operators
- Quote normalization

**Configuration:** Uses defaults (no config file needed)

### isort - Import Organizer

**Purpose:** Sorts and organizes imports
```bash
# Sort all imports
isort .

# Check without modifying
isort --check-only .
```

**What it does:**
```python
# Before:
import os
from fastapi import FastAPI
from typing import Optional
import sys
from sqlalchemy import Column

# After:
import os
import sys
from typing import Optional

from fastapi import FastAPI
from sqlalchemy import Column
```

**Order:** Standard library → Third-party → Local imports (with blank lines)

### pylint - Static Analysis

**Purpose:** Catches bugs, enforces style, suggests improvements
```bash
# Check all code
pylint activity_service.py routers/

# Check specific file
pylint routers/tasks.py

# Get score
pylint activity_service.py routers/ | grep "Your code"
```

**What it catches:**
- Unused variables
- Missing docstrings
- Complex functions (too many branches/arguments)
- Potential bugs (e.g., singleton comparisons)
- Style violations

## Configuration

### .pylintrc

Created custom config to disable overly strict rules:
```ini
[MASTER]
disable=
    C0114,  # missing-module-docstring (docstrings at file level not needed)
    C0115,  # missing-class-docstring
    C0116,  # missing-function-docstring
    R0903,  # too-few-public-methods (common with Pydantic models)
    R0913,  # too-many-arguments (FastAPI deps can have many args)
    R0914,  # too-many-locals (some functions are inherently complex)
    R0917,  # too-many-positional-arguments
    R0912,  # too-many-branches (some logic is unavoidably branchy)
    R0911,  # too-many-return-statements (early returns are good!)
    W1203,  # logging-fstring-interpolation (f-strings in logging are fine)
    R0801,  # duplicate-code (some duplication is acceptable)

[FORMAT]
max-line-length=100  # Match project convention

[BASIC]
good-names=i,j,k,db,id,_  # Common short names that are fine
```

**Why disable these?**
- **Module docstrings:** File purpose is obvious from name
- **Argument counts:** FastAPI dependencies naturally increase argument count
- **F-strings in logging:** More readable than lazy % formatting
- **Some complexity:** Real-world code has some inherent complexity

## Common Fixes

### 1. Unnecessary elif After return
```python
# ❌ Pylint complains: "Unnecessary elif after return"
if condition:
    return "A"
elif other_condition:
    return "B"

# ✅ Fixed: Use if instead of elif
if condition:
    return "A"
if other_condition:  # Changed from elif
    return "B"
```

**Why:** After `return`, code exits function. Next check is independent, not "else if".

### 2. Useless return
```python
# ❌ Pylint complains: "Useless return"
def delete_something(...):
    db.delete(item)
    db.commit()
    return None  # Unnecessary

# ✅ Fixed: Remove explicit None return
def delete_something(...):
    db.delete(item)
    db.commit()
    # Implicitly returns None
```

### 3. Unused Variables/Imports
```python
# ❌ Pylint complains: "Unused variable"
def process_data(data):
    result = expensive_calculation()  # Never used
    return data

from fastapi import HTTPException  # Never used

# ✅ Fixed: Remove unused code
def process_data(data):
    return data
```

**Auto-fix with autoflake:**
```bash
pip install autoflake
autoflake --remove-all-unused-imports --in-place -r .
```

### 4. Line Too Long
```python
# ❌ Pylint complains: Line too long (110/100)
detail = f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"

# ✅ Option 1: Extract complex expression
allowed = ', '.join(ALLOWED_EXTENSIONS)
detail = f"File type {file_ext} not allowed. Allowed types: {allowed}"

# ✅ Option 2: Break at logical boundary
detail = (
    f"File type {file_ext} not allowed. "
    f"Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
)
```

### 5. Singleton Comparison
```python
# ❌ Pylint warning: Use 'is False' for singleton
if task.completed == False:
    ...

# ✅ Fixed: Use 'is' or 'not'
if task.completed is False:  # Explicit
    ...
if not task.completed:  # Pythonic
    ...
```

## Workflow

### During Development
```bash
# Before committing
black .
isort .
pylint routers/ activity_service.py
```

### Pre-commit Hooks (Optional)

Automatically format on every commit:
```bash
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
EOF

# Install hooks
pre-commit install

# Now black/isort run automatically on git commit
```

### CI/CD Integration

Add to GitHub Actions (future improvement):
```yaml
- name: Lint code
  run: |
    pip install black isort pylint
    black --check .
    isort --check-only .
    pylint routers/ activity_service.py
```

## Type Hints & Type Checking

While not enforced with mypy, function signatures use type hints:
```python
def log_activity(
    db_session: Session,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    details: Optional[dict[str, Any]] = None
) -> ActivityLog:
    """Type hints make intent clear and enable IDE autocomplete."""
```

**Benefits:**
- IDE autocomplete
- Early error detection
- Self-documenting code

## Ignored Warnings

Some warnings are intentionally ignored:

### Import Outside Toplevel
```python
def flag_tags(task):
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "tags")
```

**Why:** Lazy import for performance (only import when needed)

### Broad Exception Caught
```python
try:
    db.execute("SELECT 1")
except Exception as e:  # Intentionally broad
    return {"status": "unhealthy"}
```

**Why:** Health checks should catch any database error

### Unused Request Argument
```python
@limiter.limit("100/hour")
def endpoint(request: Request, ...):  # request unused but required
```

**Why:** FastAPI rate limiting requires Request parameter

## Lessons Learned

**Linting isn't about perfection:**
- 10/10 score doesn't mean perfect code
- Some rules are overly strict
- Balance pragmatism with standards

**Formatting saves time:**
- No debates about style
- Consistent codebase
- Focus on logic, not formatting

**Static analysis catches real bugs:**
- Unused variables → potential logic errors
- Unreachable code → dead code removal
- Type issues → runtime errors prevented

**Configuration is personal:**
- Default rules may not fit your project
- Disable rules with good reason
- Document why rules are disabled

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [Pylint Messages Reference](https://pylint.readthedocs.io/en/latest/user_guide/messages/messages_overview.html)
- [PEP 8 Style Guide](https://pep8.org/)