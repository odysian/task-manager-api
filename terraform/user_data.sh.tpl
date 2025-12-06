#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log)
exec 2>&1
echo "=== Starting Task Manager API Setup ==="

# Install dependencies
yum update -y
yum install -y docker git postgresql15

# Start Docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Clone repo
git clone ${github_repo} /home/ec2-user/task-manager-api

# Fix ownership 
chown -R ec2-user:ec2-user /home/ec2-user/task-manager-api

cd /home/ec2-user/task-manager-api

# Create .env file
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
EOF

# Wait for RDS to be available (can take 5+ minutes after RDS resource created)
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

# Create database (idempotent - safe to run multiple times)
echo "=== Creating database ==="
PGPASSWORD='${db_password}' psql -h ${rds_endpoint} -U ${db_username} -d postgres << 'SQLEOF'
SELECT 'CREATE DATABASE ${db_name}' 
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db_name}')\gexec
SQLEOF

# Build and run Docker
echo "=== Building Docker image ==="
docker build -t taskmanager-api .

echo "=== Starting container ==="
docker run -d \
  --name taskmanager-api \
  -p 8000:8000 \
  --restart unless-stopped \
  --env-file .env \
  taskmanager-api

echo "=== Setup complete ==="