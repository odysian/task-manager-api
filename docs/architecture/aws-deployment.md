# AWS Manual Deployment Cheatsheet

Quick reference for the manual AWS deployment completed in Phase 2.

## Infrastructure Overview

**Architecture:**
```
Internet
  ↓
EC2 (t3.micro) - Docker container
  ↓ connects to ↓
RDS PostgreSQL (db.t3.micro) - Private subnet
ElastiCache Redis (cache.t3.micro) - Private subnet  
S3 Bucket - File storage
```

## Resource IDs

**VPC & Network:**
- VPC: `vpc-0b5d6c2c823eee5c4`
- Subnets: us-east-1a, us-east-1b (and 4 others)

**Security Groups:**
- EC2 SG: `sg-00e5c2ce10d384de0` (ports 22, 8000 from 0.0.0.0/0)
- RDS SG: `sg-0512d67c0fcacac0b` (port 5432 from EC2 SG only)
- Redis SG: `sg-035e8de98c7146b61` (port 6379 from EC2 SG only)

**Resources:**
- EC2: `i-057d0d9548d072790` (98.81.225.76)
- RDS: `taskmanager-db.c0fekuwkkx5w.us-east-1.rds.amazonaws.com`
- Redis: `taskmanager-redis.1dyxx9.0001.use1.cache.amazonaws.com`
- S3: `task-manager-uploads-cjc3x3`
- Key Pair: `taskmanager-key`

## Key Concepts Learned

**Environment Variables:**
- Same application code works everywhere
- Just change `DATABASE_URL` and `REDIS_URL` to point to different endpoints
- Local: Docker service names (`postgres:5432`)
- Production: AWS endpoints (RDS/ElastiCache hostnames)

**Docker on EC2:**
- Run migrations separately: `docker run --rm taskmanager-api alembic upgrade head`
- Run API: `docker run -d -p 8000:8000 --env-file .env taskmanager-api`
- Better: Use entrypoint script (implemented in Phase 3)

## Quick Commands

**SSH to EC2:**
```bash
ssh -i ~/.ssh/taskmanager-key.pem ec2-user@98.81.225.76
```

**View Container Logs:**
```bash
docker logs taskmanager-api -f
```

**Restart Container:**
```bash
docker restart taskmanager-api
```

**Run New Migration:**
```bash
cd /home/ec2-user/task-manager-api
git pull
docker stop taskmanager-api
docker rm taskmanager-api
docker build -t taskmanager-api .
docker run --rm --env-file .env taskmanager-api alembic upgrade head
docker run -d --name taskmanager-api -p 8000:8000 --env-file .env taskmanager-api
```

## Cleanup (Before Terraform)

```bash
# Terminate EC2
aws ec2 terminate-instances --instance-ids i-057d0d9548d072790 --region us-east-1

# Delete RDS
aws rds delete-db-instance --db-instance-identifier taskmanager-db --skip-final-snapshot --region us-east-1

# Delete ElastiCache  
aws elasticache delete-cache-cluster --cache-cluster-id taskmanager-redis --region us-east-1

# Delete Security Groups (after instances are gone)
aws ec2 delete-security-group --group-id sg-00e5c2ce10d384de0 --region us-east-1
aws ec2 delete-security-group --group-id sg-0512d67c0fcacac0b --region us-east-1
aws ec2 delete-security-group --group-id sg-035e8de98c7146b61 --region us-east-1
```

## Next Steps

Phase 3: Automate everything with Terraform
- All resources defined as code
- Version controlled infrastructure
- Reproducible deployments
- Easy to destroy/recreate