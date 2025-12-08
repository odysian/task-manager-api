# CI/CD

Quick reference for automated testing and deployment concepts learned while building the Task Manager API pipeline.

---

## Core Concepts

### Continuous Integration (CI)
Automatically test code changes before they reach production.

**Flow:**
1. Developer creates feature branch
2. Opens pull request to main
3. GitHub Actions runs tests automatically
4. PR shows ✅ or ❌ status
5. Only merge if tests pass

**Why:**
- Catches bugs early
- Prevents broken code in production
- Documents that code works
- Enforces testing discipline

---

### Continuous Deployment (CD)
Automatically deploy passing code to production.

**Flow:**
1. PR merged to main
2. Build Docker image
3. Push to container registry
4. Deploy to production servers
5. Verify deployment worked

**Why:**
- Fast feedback (changes live in minutes)
- Consistent deployments (same process every time)
- Less manual work
- Reduces human error

---

## GitHub Actions Basics

### Workflow Structure
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]      # When to run
  pull_request:
    branches: [main]

jobs:
  test:                   # Job name
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Run tests
        run: pytest
```

### Key Concepts

**Triggers (`on`):**
- `push` - On code push to branch
- `pull_request` - When PR opened/updated
- `workflow_dispatch` - Manual trigger button

**Jobs:**
- Run in parallel by default
- Use `needs: [job-name]` to run sequentially
- Each job gets fresh VM

**Steps:**
- Sequential commands within a job
- `uses:` runs pre-built actions
- `run:` runs shell commands

**Runners:**
- `ubuntu-latest` - Linux VM (most common)
- `windows-latest`, `macos-latest` also available
- Gets destroyed after workflow

---

## Secrets Management

### GitHub Secrets
Store sensitive data (passwords, API keys, SSH keys).

**Location:** Repo Settings → Secrets and variables → Actions

**Usage in workflow:**
```yaml
env:
  API_KEY: ${{ secrets.API_KEY }}
```

**Never:**
- Hardcode secrets in code
- Commit secrets to Git
- Echo secrets in logs

**Always:**
- Use environment variables
- Store in GitHub Secrets
- Different secrets per environment

---

## Docker in CI/CD

### Why Use Docker

**Consistency:**
- Same environment everywhere (local, CI, production)
- "Works on my machine" → "Works everywhere"

**Isolation:**
- Dependencies bundled with app
- No conflicts between projects

**Versioning:**
- Tag images with version numbers
- Easy rollback to previous versions

### Docker Build Cache

**Problem:** Building Docker images is slow (2-3 minutes)

**Solution:** Layer caching

```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Requires:**
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3
```

**Result:**
- First build: ~3 minutes
- Cached builds: ~20 seconds
- Only rebuilds changed layers

---

## Container Registries

### What They Are
Storage for Docker images (like GitHub for code, but for containers).

**GitHub Container Registry (GHCR):**
- `ghcr.io/username/repo-name:tag`
- Free for public repos
- Integrated with GitHub Actions

### Image Tagging Strategy

```
ghcr.io/odysian/task-manager-api:main          # Latest on main branch
ghcr.io/odysian/task-manager-api:latest        # Same as main
ghcr.io/odysian/task-manager-api:main-79b1393  # Specific commit
```

**Why multiple tags:**
- `main` - Always get latest
- `main-79b1393` - Specific version for rollbacks
- `latest` - Convention for "current production"

### Workflow Pattern

```yaml
# Build job
- name: Build and push
  with:
    push: true
    tags: |
      ghcr.io/user/app:main
      ghcr.io/user/app:latest
      ghcr.io/user/app:main-${{ github.sha }}

# Deploy job
- name: Pull image
  run: docker pull ghcr.io/user/app:main
```

---

## Deployment Strategies

### Rolling Deployment (Simple)
```bash
docker stop old-container
docker rm old-container
docker run new-container
```

**Downtime:** 30-60 seconds while new container starts

---

### Blue-Green Deployment (Zero Downtime)

**Process:**
1. **Blue** (old) serves traffic on port 8000
2. Start **Green** (new) on port 8001
3. Health check Green (verify it works)
4. If healthy: stop Blue, switch Green to port 8000
5. If unhealthy: kill Green, Blue keeps running

```bash
# Start Green
docker run -d --name app-green -p 8001:8000 new-image

# Health check (30 attempts, 1 second apart)
for i in {1..30}; do
  curl -f http://localhost:8001/health && break
  sleep 1
done

# Switch if healthy
docker stop app-blue
docker rm app-blue
docker run -d --name app-blue -p 8000:8000 new-image
```

**Benefits:**
- Zero downtime (~2 seconds during port switch)
- Automatic rollback if new version fails
- Safe verification before switching traffic

**Downside:**
- Requires running two containers temporarily
- More complex than simple restart

---

## SSH in GitHub Actions

### Setup

**1. Generate key pair:**
```bash
ssh-keygen -t rsa -b 4096 -f taskmanager-key
```

**2. Add public key to server:**
```bash
cat taskmanager-key.pub >> ~/.ssh/authorized_keys
```

**3. Add private key to GitHub Secrets:**
- Name: `EC2_SSH_KEY`
- Value: Contents of `taskmanager-key` (include BEGIN/END lines)

**4. Use in workflow:**
```yaml
- name: Deploy
  env:
    EC2_SSH_KEY: ${{ secrets.EC2_SSH_KEY }}
    EC2_HOST: ${{ secrets.EC2_HOST }}
  run: |
    echo "$EC2_SSH_KEY" > key.pem
    chmod 600 key.pem
    ssh -i key.pem user@$EC2_HOST "commands here"
    rm key.pem
```

### Passing Variables to Remote

**Problem:** Variables don't expand inside SSH heredoc

**Solution:** Pass through SSH command line
```bash
ssh user@host \
  "VAR1='value1' VAR2='value2' bash -s" << 'ENDSSH'
  echo $VAR1  # Available in remote shell
ENDSSH
```

**Security:** Keep quotes on heredoc (`<< 'ENDSSH'`) to prevent local expansion

---

## Health Checks

### Why They Matter
Verify application actually works before declaring success.

### What to Check
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "version": "0.1.0"
}
```

### Retry Logic
```bash
MAX_ATTEMPTS=30
ATTEMPT=0
HEALTHY=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  if curl -f http://localhost:8000/health; then
    HEALTHY=true
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  sleep 1
done

if [ "$HEALTHY" = false ]; then
  echo "Deployment failed"
  exit 1
fi
```

**Why retry:** Container might take 5-10 seconds to start

---

## Common Issues & Solutions

### "Cache export not supported"
**Problem:** Default Docker driver doesn't support cache

**Fix:**
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3
```

---

### "SSH connection timeout"
**Problem:** Security group blocking GitHub Actions IPs

**Fix:** Allow SSH from `0.0.0.0/0` (safe with key-based auth)

---

### "Cannot perform interactive login"
**Problem:** Docker login fails in non-TTY SSH session

**Fix:** Pass credentials through environment
```bash
ssh user@host "GHCR_PAT='$TOKEN' bash -s" << 'ENDSSH'
  echo "$GHCR_PAT" | docker login ghcr.io -u user --password-stdin
ENDSSH
```

---

### "Manifest unknown"
**Problem:** Image tag doesn't exist in registry

**Fix:** Use correct tag (check what build job created)
```bash
# Build creates: main-79b1393
# Deploy should use: main-79b1393 (not full SHA)
```

---

## Testing in CI

### Service Containers
Temporary databases/services for tests.

```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_PASSWORD: test_password
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
  
  redis:
    image: redis:7-alpine
```

**Access in tests:** `localhost:5432`, `localhost:6379`

### Test Database Pattern
```python
# conftest.py
TEST_DATABASE_URL = os.getenv(
  "DATABASE_URL",
  "postgresql://user:pass@localhost/test_db"
)
```

**Why:** CI can override, local dev has defaults

---

## Credential Management Across Environments

### Local Development
- `.env` file (gitignored)
- Simple passwords for convenience
- `dev_password` is fine

### CI Testing
- Hardcoded in workflow (safe - temporary environment)
- `test_password` - isolated, destroyed after tests
- No real data

### Production
- Strong random passwords (32+ chars)
- Stored in `terraform.tfvars` (gitignored)
- Terraform passes to infrastructure
- GitHub Secrets for deployment credentials

---

## Git Workflow with CI/CD

```bash
# 1. Create feature branch
git checkout -b feature/add-feature

# 2. Make changes, commit
git add .
git commit -m "Add feature"

# 3. Push to GitHub
git push origin feature/add-feature

# 4. Open pull request
# → Tests run automatically

# 5. Merge to main (if tests pass)
# → Deployment runs automatically

# 6. Update local main
git checkout main
git pull origin main
git branch -d feature/add-feature
```

---

## Best Practices

**Testing:**
- Test automatically on every PR
- Fast tests (< 2 minutes)
- Don't merge failing tests

**Building:**
- Use layer caching
- Build once, deploy everywhere
- Tag images with versions

**Deploying:**
- Zero-downtime strategy
- Health checks before declaring success
- Automatic rollback on failure

**Security:**
- Use secrets for credentials
- Different secrets per environment
- Never log secrets

**Git:**
- Feature branches for changes
- Pull requests for review
- Main always deployable

---

## Interview Talking Points

**"Tell me about your CI/CD pipeline"**
> "I built a GitHub Actions pipeline that tests code on pull requests and deploys on merge to main. The build job creates a Docker image with layer caching (3min → 20sec), pushes to GitHub Container Registry. The deploy job uses blue-green strategy for zero downtime - new version starts on a different port, health checks verify it works, then traffic switches over. If health checks fail, it automatically rolls back."

**"What's blue-green deployment?"**
> "It's a zero-downtime strategy where you run two versions simultaneously. The old version serves traffic while the new version starts on a different port. You health check the new version to make sure it actually works, then switch traffic over. If the new version fails health checks, you kill it and the old version keeps running - instant rollback with no user impact."

**"How do you handle secrets?"**
> "Never commit secrets to Git. Use environment variables and store values in GitHub Secrets for CI/CD. Different secrets for each environment - local dev uses simple passwords in a gitignored .env file, production uses strong random passwords managed by Terraform."

---

**Last Updated:** December 3, 2025  
**Status:** CI/CD pipeline implemented and working in production