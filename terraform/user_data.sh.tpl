#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log)
exec 2>&1

# Force update: 2024-12-21
echo "=== Starting Task Manager API Setup ==="

# ============================================
# PHASE 1: Install dependencies
# ============================================
echo "=== Installing system packages ==="
yum update -y
yum install -y docker git postgresql15 nginx certbot python3-certbot-nginx

# ============================================
# PHASE 2: Start services
# ============================================
echo "=== Starting Docker ==="
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

echo "=== Starting NGINX ==="
systemctl start nginx
systemctl enable nginx

# ============================================
# PHASE 3: Clone repository
# ============================================
echo "=== Cloning repository ==="
git clone ${github_repo} /home/ec2-user/task-manager-api

# Fix ownership 
chown -R ec2-user:ec2-user /home/ec2-user/task-manager-api
cd /home/ec2-user/task-manager-api

# ============================================
# PHASE 4: Create environment file
# ============================================
echo "=== Creating .env file ==="
cat > .env << 'EOF'
SECRET_KEY=${secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
DATABASE_URL=postgresql://${db_username}:${db_password}@${rds_endpoint}:5432/${db_name}
REDIS_URL=redis://${redis_endpoint}:6379/0
AWS_ACCESS_KEY_ID=${aws_access_key_id}
AWS_SECRET_ACCESS_KEY=${aws_secret_access_key}
AWS_REGION=${aws_region}
S3_BUCKET_NAME=${s3_bucket_name}
MAX_UPLOAD_SIZE=10485760
ALLOWED_EXTENSIONS=.jpg,.jpeg,.png,.gif,.pdf,.txt,.doc,.docx
RATE_LIMIT_ENABLED=true
TESTING=false
ENVIRONMENT=production
SNS_TOPIC_ARN=${sns_topic_arn}
FRONTEND_URL=https://${frontend_domain}
EOF

# ============================================
# PHASE 5: Wait for RDS
# ============================================
echo "=== Waiting for RDS ==="
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if PGPASSWORD='${db_password}' psql -h ${rds_endpoint} -U ${db_username} -d postgres -c '\l' > /dev/null 2>&1; then
        echo "RDS is ready"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS"
    sleep 10
done

# ============================================
# PHASE 6: Create database
# ============================================
echo "=== Creating database ==="
PGPASSWORD='${db_password}' psql -h ${rds_endpoint} -U ${db_username} -d postgres << 'SQLEOF'
SELECT 'CREATE DATABASE ${db_name}' 
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db_name}')\gexec
SQLEOF

# ============================================
# PHASE 7: Configure NGINX reverse proxy
# ============================================
echo "=== Configuring NGINX ==="
cat > /etc/nginx/conf.d/api.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name ${backend_domain};

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
NGINX_EOF

# Test and reload NGINX
echo "=== Testing NGINX configuration ==="
nginx -t
systemctl reload nginx

# ============================================
# PHASE 8: Build and run Docker
# ============================================
echo "=== Building Docker image ==="
docker build -t taskmanager-api .

# Stop any existing container (idempotent)
docker stop taskmanager-api 2>/dev/null || true
docker rm taskmanager-api 2>/dev/null || true

echo "=== Starting container ==="
docker run -d \
  --name taskmanager-api \
  -p 8000:8000 \
  --restart unless-stopped \
  --env-file .env \
  taskmanager-api

# ============================================
# PHASE 9: Wait for FastAPI to be healthy
# ============================================
echo "=== Waiting for FastAPI to be healthy ==="
MAX_HEALTH_ATTEMPTS=30
HEALTH_ATTEMPT=0
while [ $HEALTH_ATTEMPT -lt $MAX_HEALTH_ATTEMPTS ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "FastAPI is healthy"
        break
    fi
    HEALTH_ATTEMPT=$((HEALTH_ATTEMPT + 1))
    echo "Health check attempt $HEALTH_ATTEMPT/$MAX_HEALTH_ATTEMPTS"
    sleep 5
done

if [ $HEALTH_ATTEMPT -eq $MAX_HEALTH_ATTEMPTS ]; then
    echo "WARNING: FastAPI health check failed, but continuing with SSL setup"
fi

# ============================================
# PHASE 10: Get SSL certificate
# ============================================
echo "=== Obtaining SSL certificate ==="
certbot --nginx \
    -d ${backend_domain} \
    --non-interactive \
    --agree-tos \
    --email ${ssl_email} \
    --redirect

# Certbot automatically:
# - Gets certificate from Let's Encrypt
# - Updates NGINX config to use HTTPS
# - Sets up HTTP -> HTTPS redirect
# - Configures auto-renewal

# ============================================
# PHASE 11: Enable auto-renewal
# ============================================
echo "=== Setting up SSL auto-renewal ==="
systemctl enable certbot-renew.timer
systemctl start certbot-renew.timer

# Final NGINX reload to ensure HTTPS is active
systemctl reload nginx

echo "=== Setup complete ==="
echo "Backend API: https://${backend_domain}"
echo "Health check: https://${backend_domain}/health"
echo "Logs: /var/log/user-data.log"