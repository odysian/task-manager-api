# ============================================
# DOCKER DEBUGGING CHEATSHEET
# ============================================

# --- CONTAINERS ---
docker ps -a                              # All containers
docker ps                                 # Running containers only
docker logs <container-id> --tail 100    # View logs
docker logs -f <container-id>            # Follow logs live
docker exec -it <container-id> bash      # Get shell inside
docker restart <container-id>            # Restart container
docker inspect <container-id>            # Detailed info

# --- COMMON CONTAINER NAMES ---
# API: task-manager-api, taskmanager-api, or random ID
# DB:  taskmanager-postgres, postgres, task-manager-db
# Redis: taskmanager-redis, redis

# --- DATABASE (DOCKER) ---
# Find postgres container first:
docker ps -a | grep postgres

# Connect to database:
docker exec -it <postgres-container> psql -U task_user -d task_manager

# Quick query without entering shell:
docker exec <postgres-container> psql -U task_user -d task_manager -c "SELECT COUNT(*) FROM users;"

# --- DATABASE (RDS) ---
# Get endpoint from AWS Console or:
aws rds describe-db-instances --query 'DBInstances[0].Endpoint.Address'

# Connect:
psql -h <endpoint>.rds.amazonaws.com -U task_user -d task_manager

# --- PSQL COMMANDS (once connected) ---
\l                    # List databases
\c task_manager       # Connect to database
\dt                   # List tables
\d users              # Describe table structure
\q                    # Exit

# Common queries:
SELECT * FROM users LIMIT 5;
SELECT COUNT(*) FROM tasks;
SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 10;

# --- NETWORK ---
docker network ls                        # List networks
docker network inspect <network-name>   # Network details
nc -zv localhost 5432                   # Test PostgreSQL port
nc -zv localhost 6379                   # Test Redis port

# --- ENVIRONMENT ---
docker exec <container-id> env                    # All env vars
docker exec <container-id> env | grep AWS        # AWS creds
docker exec <container-id> env | grep DATABASE   # DB connection

# --- FILES ---
docker exec <container-id> ls -la /              # Root directory
docker exec <container-id> cat /app/.env         # View .env file
docker exec <container-id> cat /app/main.py      # View code

# --- CLEANUP ---
docker system df                  # Disk usage
docker image prune -a            # Remove unused images
docker container prune           # Remove stopped containers
df -h                            # System disk space

# --- FIND THINGS ---
# Find API container:
docker ps | grep -E "api|task-manager|faros"

# Find database container:
docker ps -a | grep -E "postgres|db"

# Find what's using a port:
sudo netstat -tlnp | grep 8000   # API port
sudo netstat -tlnp | grep 5432   # Postgres port

# --- TROUBLESHOOTING ---
# Container won't start:
docker logs <container-id>
docker inspect <container-id> | grep -A 10 State

# Database connection failed:
docker exec <api-container> ping <db-container-name>
docker network inspect bridge

# Out of space:
df -h
docker system prune -a

# Check if service exists (non-Docker):
sudo systemctl list-units --type=service | grep -E "postgres|taskmanager"