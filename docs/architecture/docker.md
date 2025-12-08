# Docker & Containerization

This project uses Docker to package a FastAPI application, PostgreSQL database, and Redis cache into portable containers that run consistently in local development (Docker Compose) and production (EC2 via GitHub Actions).

-----

## 1\. Core Concepts

  * **Image:** The "blueprint" or "recipe" (read-only). Built from a `Dockerfile`.
      * *Analogy:* The frozen meal package.
  * **Container:** The running instance of an image.
      * *Analogy:* The meal being cooked and eaten.
  * **Volume:** Persistent storage that survives when a container dies.
      * *Usage:* Storing Postgres data (`/var/lib/postgresql/data`) so you don't lose users when restarting.
  * **Network:** An internal private network allowing containers to talk to each other by name (e.g., `api` can reach `postgres`).

-----

## 2\. The Dockerfile (`Dockerfile`)

Your recipe for building the API image.

| Instruction | Code in Repo | Purpose | Best Practice |
| :--- | :--- | :--- | :--- |
| **FROM** | `FROM python:3.12-slim` | Sets the OS and Python version. | Use `-slim` or `-alpine` to keep images small and secure. |
| **WORKDIR** | `WORKDIR /app` | Sets the default directory for commands. | Always set this so you know where your files land. |
| **COPY (Deps)** | `COPY requirements.txt .` | copies *only* requirements first. | **Layer Caching:** If `requirements.txt` hasn't changed, Docker skips `pip install` on rebuilds. |
| **RUN** | `RUN pip install ...` | Installs dependencies. | Use `--no-cache-dir` to keep image size down. |
| **COPY (App)** | `COPY . .` | Copies the rest of your code. | Done *after* dependencies so code changes don't trigger re-installs. |
| **ENTRYPOINT** | `ENTRYPOINT ["./entrypoint.sh"]` | The script that runs when the container starts. | Use shell scripts to handle migration commands or setup before the app starts. |

-----

## 3\. Docker Compose (`docker-compose.yml`)

Orchestrates multiple containers for local development.

### Key Services

  * **`postgres`:** The database.
      * *Healthcheck:* `pg_isready` ensures the DB is awake before the API tries to connect.
      * *Volumes:* `postgres_data:/var/lib/postgresql/data` persists data.
  * **`redis`:** The cache.
      * *Healthcheck:* `redis-cli ping` ensures availability.
  * **`api`:** Your FastAPI app.
      * *Depends On:* `condition: service_healthy` waits for DB/Redis to be "green" before starting.
      * *Hot Reload:* `uvicorn ... --reload` lets you code without restarting containers.

### Networking Magic

In Docker Compose, service names become hostnames:

  * **Wrong:** `localhost:5432` (Looks inside the API container itself)
  * **Correct:** `postgres:5432` (Routes to the Postgres container)

-----

## 4\. CI/CD & Production (`deploy.yml`)

How we ship containers to the world.

### The Build Pipeline (GitHub Actions)

1.  **Buildx:** High-performance Docker builder used by GitHub.
2.  **GHCR (GitHub Container Registry):** Where we store our images (`ghcr.io/odysian/task-manager-api`).
3.  **Caching:** `cache-from: type=gha` speeds up builds by reusing layers from previous GitHub Action runs.

### The Deployment (EC2)

1.  **Login:** `docker login ghcr.io ...` authenticates the server to pull private images.
2.  **Pull:** `docker pull ...` downloads the new image while the old app is still running (Zero Downtime prep).
3.  **Run Migrations:** `docker run --rm ... alembic upgrade head` updates the DB schema using an ephemeral container (it runs once and deletes itself).
4.  **Swap:** Stop old container -\> Start new container.

-----

## 5\. Essential Commands

### Build & Run (Local)

```bash
# Start all services in the background
docker-compose up -d

# Force a rebuild (if you changed Dockerfile)
docker-compose up -d --build

# View logs for the API service
docker-compose logs -f api

# Stop everything
docker-compose down
```

### Debugging & Maintenance

```bash
# "SSH" into a running container
docker exec -it taskmanager-api /bin/bash

# See running containers
docker ps

# See all containers (including stopped ones)
docker ps -a

# Nuke everything (Clean slate)
# WARNING: Deletes all stopped containers, unused networks, and dangling images
docker system prune -a
```

### Database Management via Docker

```bash
# Connect to the running Postgres DB inside Docker
docker exec -it taskmanager-postgres psql -U task_user -d task_manager
```

-----

## 6\. Pro-Tips & "Gotchas"

1.  **.dockerignore is Critical:**
      * Always ignore `venv/`, `.git/`, and `__pycache__/`.
      * *Why?* Keeps the image small and prevents local trash files from breaking the container.
2.  **Environment Variables:**
      * **Local:** Loaded from `.env` by Docker Compose.
      * **Production:** Passed via `--env-file .env` in the `docker run` command on EC2.
3.  **PID 1 & Signals:**
      * When you run `docker stop`, Docker sends a `SIGTERM` signal to the process with ID 1.
      * If your app ignores this, Docker waits 10s and kills it hard (`SIGKILL`).
      * *Fix:* FastAPI handles this well, but ensure your `entrypoint.sh` uses `exec` to pass signals correctly.
4.  **Root vs. User:**
      * Currently, your container runs as `root` (default).
      * *Next Level:* Create a non-root user in the Dockerfile for better security (Phase 2 optimization).