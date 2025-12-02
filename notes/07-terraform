# Phase 6: Terraform Deployment Cheatsheet

Personal reference for AWS infrastructure automation, user data bootstrapping, and production deployment patterns.

---

## Table of Contents
- [Terraform Infrastructure Overview](#terraform-infrastructure-overview)
- [User Data Bootstrap Scripts](#user-data-bootstrap-scripts)
- [IAM Roles for Applications](#iam-roles-for-applications)
- [Docker Entrypoint Pattern](#docker-entrypoint-pattern)
- [Idempotent Operations](#idempotent-operations)
- [Terraform Templating](#terraform-templating)
- [Resource Dependencies](#resource-dependencies)
- [Debugging Production Deployments](#debugging-production-deployments)

---

## Terraform Infrastructure Overview

### What We Automated

**13 AWS resources** managed as code:
- 3 Security Groups (EC2, RDS, Redis)
- 2 Subnet Groups (RDS, ElastiCache)
- 1 RDS PostgreSQL instance
- 1 ElastiCache Redis cluster
- 1 EC2 instance
- 4 IAM resources (role, policy, attachment, instance profile)

### Project Structure

```
terraform/
├── main.tf              # Provider, VPC/subnet data sources
├── variables.tf         # 13 input variables
├── terraform.tfvars     # Secret values (gitignored!)
├── outputs.tf           # URLs, IPs, connection strings
├── security_groups.tf   # Network isolation rules
├── rds.tf              # PostgreSQL database
├── elasticache.tf      # Redis cache
├── ec2.tf              # App server + IAM configuration
└── user_data.sh.tpl    # Bootstrap script template
```

### Key Pattern: Separate Concerns

**Why split into multiple files?**
- Easier to find resources (all security groups in one file)
- Can reuse patterns across projects
- Team members can work on different files
- Clear separation: networking, compute, data, IAM

---

## User Data Bootstrap Scripts

### What is User Data?

**User data** = Script that runs **once** when EC2 instance first boots.

**Purpose:** Automate server setup so you don't have to SSH in and configure manually.

### Our Bootstrap Script Flow

```bash
1. Set up logging → All output to /var/log/user-data.log
2. Install dependencies → Docker, Git, PostgreSQL client
3. Start Docker → Enable service, add user to docker group
4. Clone repository → Get latest code from GitHub
5. Create .env file → Inject secrets and endpoints
6. Wait for RDS → Loop until database is available
7. Create database → Idempotently create application database
8. Build Docker image → From Dockerfile in repo
9. Run container → Start application with environment variables
```

### Logging Setup (Critical for Debugging)

```bash
#!/bin/bash
set -e  # Exit on any error

# Redirect all output to log file
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting user data script at $(date)"
```

**What this does:**
- `exec >` - Redirects all standard output
- `tee` - Writes to both log file AND next command
- `logger -t user-data` - Sends to system log with tag
- `-s 2>/dev/console` - Also shows on console for debugging
- `2>&1` - Include error output too

**Why critical:**
- Can't see terminal output when script runs on boot
- SSH in later and run `sudo tail -f /var/log/user-data.log`
- See exactly where script succeeded or failed

### Installing Dependencies

```bash
echo "Installing dependencies..."
yum update -y
yum install -y docker git postgresql15

echo "Starting Docker..."
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user
```

**Key points:**
- `-y` flag: Auto-approve installations (no manual confirmation)
- `systemctl enable`: Start Docker on every boot (not just this boot)
- `usermod -a -G`: Add ec2-user to docker group (run docker without sudo)

### Creating Environment File with Heredoc

```bash
echo "Creating .env file..."
cat > .env << 'EOF'
SECRET_KEY=${secret_key}
DATABASE_URL=postgresql://${db_username}:${db_password}@${rds_endpoint}:5432/${db_name}
REDIS_URL=redis://${redis_endpoint}:6379/0
AWS_REGION=${aws_region}
S3_BUCKET_NAME=${s3_bucket_name}
EOF
```

**Heredoc syntax breakdown:**
- `cat >` - Write to file
- `<< 'EOF'` - Start heredoc (quotes prevent bash variable expansion)
- `${variable}` - Terraform will replace these (not bash)
- `EOF` - End heredoc

**Why use quotes around EOF?**
```bash
# WITH quotes: 'EOF'
# Bash won't expand $variables
# Terraform will replace ${variables}
cat > .env << 'EOF'
SECRET_KEY=${secret_key}  # Terraform replaces this
LOCAL_VAR=$HOME           # This stays as literal "$HOME"
EOF

# WITHOUT quotes: EOF
# Bash expands $variables FIRST
# Terraform gets already-expanded text
cat > .env << EOF
SECRET_KEY=${secret_key}  # Bash tries to expand, gets empty string
LOCAL_VAR=$HOME           # Bash expands to /root
EOF
```

**Rule:** Use `<< 'EOF'` when you want Terraform to do the variable injection.

---

## Waiting for RDS Availability

### The Problem

EC2 boots faster than RDS becomes available (~1 min vs ~5 min).

User data script would try to connect to RDS before it's ready → fail.

### The Solution: Wait Loop

```bash
echo "Waiting for RDS to be available..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  if PGPASSWORD='${db_password}' psql -h ${rds_endpoint} -U ${db_username} -d postgres -c '\q' 2>/dev/null; then
    echo "RDS is available!"
    break
  fi
  echo "Attempt $((ATTEMPT + 1))/$MAX_ATTEMPTS: RDS not ready, waiting 10 seconds..."
  sleep 10
  ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  echo "ERROR: RDS did not become available after $MAX_ATTEMPTS attempts"
  exit 1
fi
```

**How it works:**
- `while [ $ATTEMPT -lt $MAX_ATTEMPTS ]` - Loop up to 30 times
- `psql -c '\q'` - Try to connect and immediately quit
- `2>/dev/null` - Hide error messages (we're expecting failures)
- `if ... then break` - Exit loop when connection succeeds
- `sleep 10` - Wait 10 seconds between attempts
- Total wait time: 30 attempts × 10 seconds = 5 minutes max

**Why connect to `postgres` database?**
- Every PostgreSQL server has a default `postgres` database
- Our application database doesn't exist yet
- Can't connect to database that doesn't exist
- So connect to default, then create ours

### Setting Password for psql

```bash
PGPASSWORD='${db_password}' psql -h ${rds_endpoint} -U ${db_username} -d postgres
```

**Why `PGPASSWORD` environment variable?**
- `psql` needs password but we're in non-interactive script
- Can't type password manually during boot
- `PGPASSWORD` is PostgreSQL's way to provide password in scripts
- Single-use: Only set for this one command

**Alternative (worse) approaches:**
```bash
# DON'T DO THIS - creates security risk
echo "${db_password}" > ~/.pgpass
psql ...

# DON'T DO THIS - password visible in process list
psql -h ${rds_endpoint} -U ${db_username} -d postgres --password=${db_password}
```

---

## Idempotent Operations

### What Does Idempotent Mean?

**Idempotent** = Safe to run multiple times, same result every time.

**Examples:**
- ✅ Idempotent: "Set volume to 50%" - can run 100 times, still 50%
- ❌ Not idempotent: "Increase volume by 10%" - run 100 times = very loud!

### Why It Matters for Bootstrap Scripts

User data script runs on:
- First boot (normal)
- Instance reboot (if you restart EC2)
- Instance replacement (if Terraform recreates EC2)

Script must be **safe to run multiple times** without breaking.

### Creating Database Idempotently

```bash
PGPASSWORD='${db_password}' psql -h ${rds_endpoint} -U ${db_username} -d postgres << 'SQL'
SELECT 'CREATE DATABASE ${db_name}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db_name}')\gexec
SQL
```

**Breaking it down:**

1. **Connect to postgres database** (the default database)

2. **SQL logic:**
```sql
SELECT 'CREATE DATABASE task_manager'  -- Generate SQL command
WHERE NOT EXISTS (                      -- Only if database doesn't exist
  SELECT FROM pg_database               -- Check system catalog
  WHERE datname = 'task_manager'        -- Look for our database name
)\gexec                                 -- Execute the generated command
```

3. **`\gexec` magic:**
- Special PostgreSQL meta-command
- Takes output of SELECT and executes it as SQL
- If WHERE clause is false, SELECT returns nothing, `\gexec` does nothing

**Result:**
- First run: Database doesn't exist → SELECT returns CREATE command → `\gexec` runs it
- Second run: Database exists → WHERE clause is false → SELECT returns nothing → No error!

### Pattern for Other Idempotent Operations

```bash
# Create user only if doesn't exist
CREATE USER IF NOT EXISTS username;

# Create table only if doesn't exist
CREATE TABLE IF NOT EXISTS tasks (...);

# Install package only if not installed
yum install -y package_name  # yum is smart, skips if installed

# Start service (safe to run multiple times)
systemctl start docker  # Does nothing if already running
```

**General principle:** Check if thing exists before creating it.

---

## IAM Roles for Applications

### The Problem: Hardcoded Credentials

**Bad approach (what we DON'T do):**
```python
# In application code
s3_client = boto3.client(
    's3',
    aws_access_key_id='AKIAIOSFODNN7EXAMPLE',      # BAD!
    aws_secret_access_key='wJalrXUtnFEMI/K7MDENG'  # BAD!
)
```

**Why bad:**
- Credentials in code/env vars can leak (Git, logs, process list)
- Must rotate manually when they expire
- Hard to change without redeploying
- If stolen, attacker has permanent access

### The Solution: IAM Roles with Instance Profiles

**Good approach:**
```python
# In application code
s3_client = boto3.client('s3')  # No credentials!
# boto3 automatically gets credentials from instance metadata
```

**How it works:**

```
┌─────────────────────────────────────────────────────────┐
│ EC2 Instance                                            │
│                                                         │
│  Application (Python/boto3)                            │
│         ↓                                               │
│  "I need AWS credentials to access S3"                 │
│         ↓                                               │
│  Instance Metadata Service (169.254.169.254)           │
│         ↓                                               │
│  "Here are temporary credentials (valid 6 hours)"      │
└─────────────────────────────────────────────────────────┘
         ↓
    IAM Service
         ↓
    "EC2 has instance profile → attached to IAM role
     → role has S3 policy → credentials granted!"
```

### Setting Up IAM for EC2

**Step 1: Trust Policy (Who can assume this role?)**

```hcl
# ec2.tf
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
```

**Translation:** "Allow EC2 service to assume this role"

**Step 2: Create IAM Role**

```hcl
resource "aws_iam_role" "ec2_role" {
  name               = "taskmanager-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}
```

**Step 3: Permissions Policy (What can this role do?)**

```hcl
data "aws_iam_policy_document" "ec2_s3_access" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject", 
      "s3:DeleteObject"
    ]
    resources = ["arn:aws:s3:::${var.s3_bucket_name}/*"]
  }
}

resource "aws_iam_policy" "ec2_s3_policy" {
  name   = "taskmanager-ec2-s3-policy"
  policy = data.aws_iam_policy_document.ec2_s3_access.json
}
```

**Translation:** "Allow put/get/delete on objects in our S3 bucket"

**Step 4: Attach Policy to Role**

```hcl
resource "aws_iam_role_policy_attachment" "ec2_s3_attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_s3_policy.arn
}
```

**Step 5: Create Instance Profile (Connector)**

```hcl
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "taskmanager-ec2-profile"
  role = aws_iam_role.ec2_role.name
}
```

**Step 6: Attach to EC2**

```hcl
resource "aws_instance" "api" {
  ami                  = data.aws_ami.amazon_linux_2023.id
  instance_type        = "t3.micro"
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name
  # ... other config
}
```

### The Full Flow

```
1. Application calls boto3.client('s3')
2. boto3 checks: "Any credentials in env vars?" → No
3. boto3 checks: "Running on EC2?" → Yes
4. boto3 queries: http://169.254.169.254/latest/meta-data/iam/security-credentials/
5. Gets: Temporary credentials (access key, secret key, session token)
6. Uses credentials to sign S3 request
7. AWS validates: "These credentials from role taskmanager-ec2-role?"
8. AWS checks: "Role has permission for s3:PutObject on this bucket?"
9. Request succeeds or fails based on policy
```

### Benefits

✅ **Automatic rotation** - AWS rotates credentials every 6 hours  
✅ **No secrets in code** - Application doesn't know credentials exist  
✅ **Easy to update** - Change policy without touching application  
✅ **Follows principle of least privilege** - Only S3 access, nothing else  
✅ **Works across environments** - Same code works on any EC2 with right role  

---

## Docker Entrypoint Pattern

### The Problem: When Do Migrations Run?

**Migrations must run:**
- Before application starts (app expects database schema to exist)
- Every time we deploy (new code might have new migrations)
- Only once (don't want to run migrations multiple times simultaneously)

**Where migrations could run:**
1. ❌ User data script - only runs on first boot, not on code updates
2. ❌ Manually via SSH - error-prone, not automated
3. ✅ **Container entrypoint** - runs every time container starts

### Docker Entrypoint vs CMD

**CMD** (what we had before):
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
- Simple command to start application
- No pre-flight checks or setup

**ENTRYPOINT** (what we use now):
```dockerfile
ENTRYPOINT ["./entrypoint.sh"]
```
- Runs script before application starts
- Script can do setup, then start application

### Our Entrypoint Script

```bash
#!/bin/bash
set -e  # Exit on any error

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
```

**Key points:**

**`set -e`** - Exit immediately if any command fails
- If migrations fail, container exits (don't start broken app)
- Prevents cascading failures

**`exec`** - Replace shell process with uvicorn
- Shell (PID 1) becomes uvicorn (PID 1)
- Docker signals (stop/restart) go directly to uvicorn
- Clean shutdown when container stops

### Adding Entrypoint to Dockerfile

```dockerfile
# Copy entrypoint script
COPY entrypoint.sh .

# Make it executable
RUN chmod +x entrypoint.sh

# Set as entrypoint
ENTRYPOINT ["./entrypoint.sh"]
```

**Why `chmod +x`?**
- Files copied into container aren't executable by default
- Must explicitly mark as executable
- Alternative: `RUN chmod 755 entrypoint.sh` (rwxr-xr-x)

### Flow Comparison

**Before (CMD only):**
```
docker run → uvicorn starts → app tries to access database → 
ERROR: table doesn't exist (migrations never ran)
```

**After (ENTRYPOINT + migrations):**
```
docker run → entrypoint.sh starts → 
alembic upgrade head (creates/updates tables) → 
uvicorn starts → app works!
```

### When Container Restarts

```bash
# First start
docker run ... → Run migrations (create tables) → Start app

# Stop container
docker stop taskmanager-api

# Start same container again
docker start taskmanager-api → Run migrations (no changes, fast) → Start app

# Deploy new code
docker rm -f taskmanager-api
docker run ... → Run migrations (apply new migrations) → Start app
```

**Idempotency matters here too:**
- Running same migration twice is safe (Alembic tracks what's applied)
- If migration already applied, Alembic says "already at head" and continues

---

## Terraform Templating

### The Problem: Dynamic Values in Static Files

User data script needs:
- RDS endpoint (unknown until Terraform creates it)
- Redis endpoint (unknown until Terraform creates it)
- Secrets from variables (different per environment)

Can't hardcode these - they don't exist when we write the script!

### The Solution: Template Files

**1. Create template file** with placeholders:

```bash
# user_data.sh.tpl
DATABASE_URL=postgresql://${db_username}:${db_password}@${rds_endpoint}:5432/${db_name}
REDIS_URL=redis://${redis_endpoint}:6379/0
```

**2. Use `templatefile()` function** in Terraform:

```hcl
# ec2.tf
resource "aws_instance" "api" {
  # ... other config ...
  
  user_data = base64encode(templatefile("${path.module}/user_data.sh.tpl", {
    github_repo           = var.github_repo
    secret_key            = var.secret_key
    db_username           = var.db_username
    db_password           = var.db_password
    db_name               = var.db_name
    rds_endpoint          = aws_db_instance.postgres.address
    redis_endpoint        = aws_elasticache_cluster.redis.cache_nodes[0].address
    aws_access_key_id     = var.aws_access_key_id
    aws_secret_access_key = var.aws_secret_access_key
    aws_region            = var.aws_region
    s3_bucket_name        = var.s3_bucket_name
  }))
}
```

**3. Terraform replaces placeholders** when creating EC2:

```bash
# Result after Terraform processes template:
DATABASE_URL=postgresql://task_user:securepass123@taskmanager-db.abc123.us-east-1.rds.amazonaws.com:5432/task_manager
REDIS_URL=redis://taskmanager-redis.abc123.0001.use1.cache.amazonaws.com:6379/0
```

### Template Syntax

**In template file** (`user_data.sh.tpl`):
```bash
${variable_name}       # Single value
${var.field}           # Access struct field
${resource.name.attr}  # Reference resource attribute
```

**In Terraform** (`ec2.tf`):
```hcl
templatefile("path/to/template.tpl", {
  variable_name = "value"
  var           = some_object
})
```

### Why `base64encode()`?

```hcl
user_data = base64encode(templatefile(...))
```

**AWS requires user data in base64:**
- Ensures special characters don't break
- Handles binary data safely
- Standard format for all user data

**Terraform handles decoding:**
- AWS automatically decodes before running
- Script runs as plain text on EC2

### Template vs Heredoc in User Data

**Option 1: Template file (what we use)**
```hcl
user_data = base64encode(templatefile("user_data.sh.tpl", {...}))
```
✅ Clean separation (script in own file)  
✅ Easy to test script locally  
✅ Syntax highlighting in editor  
✅ Reusable across projects  

**Option 2: Inline heredoc**
```hcl
user_data = base64encode(<<-EOF
  #!/bin/bash
  echo "Hello"
EOF
)
```
✅ Everything in one file  
❌ Hard to read for long scripts  
❌ No syntax highlighting  
❌ Harder to test  

**Rule of thumb:** Script > 10 lines → Use template file

---

## Resource Dependencies

### The Problem: Creation Order Matters

Can't create EC2 before security group (needs SG to assign).  
Can't connect to RDS before it exists.  
Can't use Redis endpoint before ElastiCache is ready.

### Implicit Dependencies

Terraform detects most dependencies automatically:

```hcl
resource "aws_instance" "api" {
  vpc_security_group_ids = [aws_security_group.ec2.id]
  # ↑ Terraform sees this reference
  # Automatically creates security group first
}
```

**How it works:**
- Terraform parses all `.tf` files
- Builds dependency graph
- Resource references create edges in graph
- Executes in topologically sorted order

### Explicit Dependencies

Sometimes Terraform can't detect dependencies:

```hcl
resource "aws_instance" "api" {
  # ... config ...
  
  # User data references RDS endpoint via template
  # But Terraform doesn't parse template file deeply enough
  # So we tell it explicitly:
  depends_on = [
    aws_db_instance.postgres,
    aws_elasticache_cluster.redis
  ]
}
```

**When to use `depends_on`:**
- Resource A needs resource B to be **fully created and available**
- Not just exist, but actually ready to use
- Example: Database must be accepting connections, not just in "creating" state

### Our Dependency Chain

```
1. VPC (existing, data source)
   ↓
2. Security Groups (no dependencies)
   ↓
3. Subnet Groups (need VPC)
   ↓
4. RDS + ElastiCache (need security groups, subnet groups)
   ↓
5. IAM Role + Policy (no dependencies on infrastructure)
   ↓
6. EC2 (needs security group, IAM instance profile, depends_on RDS/Redis)
   ↓
7. User data script runs (waits for RDS to be available)
```

### Viewing Dependencies

```bash
# Generate visual graph
terraform graph | dot -Tpng > graph.png

# Show creation order
terraform plan
# Look for "Plan: X to add" - shows order
```

### Common Dependency Mistakes

**Mistake 1: Circular dependency**
```hcl
resource "aws_security_group" "a" {
  ingress {
    security_groups = [aws_security_group.b.id]  # A depends on B
  }
}

resource "aws_security_group" "b" {
  ingress {
    security_groups = [aws_security_group.a.id]  # B depends on A
  }
}
# ERROR: Cycle detected!
```

**Solution:** Use separate ingress rules added after creation.

**Mistake 2: Missing explicit dependency**
```hcl
resource "null_resource" "run_ansible" {
  # Runs Ansible playbook
  # Playbook configures database
  # But Terraform doesn't know this needs RDS!
  
  # Add:
  depends_on = [aws_db_instance.postgres]
}
```

---

## Debugging Production Deployments

### Bootstrap Script Debugging

**Check if script ran:**
```bash
ssh -i ~/.ssh/key.pem ec2-user@<IP>
sudo cat /var/log/user-data.log
```

**Watch script in real-time:**
```bash
sudo tail -f /var/log/user-data.log
# Wait and watch as script executes
```

**Check cloud-init status:**
```bash
sudo cloud-init status
# Output: "status: done" when complete
# Output: "status: running" if still executing
```

**Common issues:**

**Script still running:**
```bash
sudo cloud-init status
# status: running
# Be patient, RDS takes ~5 minutes
```

**Script failed:**
```bash
sudo cat /var/log/user-data.log | grep -i error
# Look for error messages
# Check which command failed (set -e exits on first error)
```

**Docker container not running:**
```bash
docker ps -a  # Show all containers, including stopped
docker logs taskmanager-api  # View container logs
```

### Application Debugging

**Check if app is listening:**
```bash
curl http://localhost:8000
# Should return {"message": "Task Manager API", "status": "running"}
```

**Check app logs:**
```bash
docker logs taskmanager-api
docker logs -f taskmanager-api  # Follow logs
```

**Check database connectivity:**
```bash
# From EC2
PGPASSWORD='password' psql -h <rds-endpoint> -U task_user -d task_manager -c '\dt'
# Should list tables (users, tasks, task_files, alembic_version)
```

**Check Redis connectivity:**
```bash
# From EC2
redis-cli -h <redis-endpoint> ping
# Should return: PONG
```

### Security Group Debugging

**Can't access API from internet:**
```bash
# Check security group allows port 8000 from 0.0.0.0/0
aws ec2 describe-security-groups --group-ids <sg-id>
```

**RDS connection refused:**
```bash
# Check RDS security group allows PostgreSQL (5432) from EC2 security group
# Not from IP address - from security group!
```

### IAM Debugging

**S3 access denied:**
```bash
# From EC2, test S3 access
aws s3 ls s3://bucket-name/
# If error, check:
# 1. Instance profile attached to EC2?
aws ec2 describe-instances --instance-ids <id> --query 'Reservations[0].Instances[0].IamInstanceProfile'

# 2. Role has S3 policy?
aws iam list-attached-role-policies --role-name taskmanager-ec2-role

# 3. Policy has correct permissions?
aws iam get-policy-version --policy-arn <arn> --version-id <version>
```

### Common Production Issues

**Issue 1: Migrations fail**
```
Error: could not connect to database
```
**Solution:** Wait for RDS to be available, check credentials in .env

**Issue 2: Container exits immediately**
```bash
docker ps -a  # Shows container exited
docker logs taskmanager-api  # Shows error
```
**Common causes:**
- Missing environment variable
- Alembic migration failed
- Database doesn't exist

**Issue 3: 502 Bad Gateway**
**Cause:** Application not running on port 8000
**Check:**
```bash
docker ps  # Is container running?
curl localhost:8000  # Does local request work?
```

**Issue 4: Works locally, not in production**
**Checklist:**
- [ ] Environment variables set correctly?
- [ ] Database migrations applied?
- [ ] Security groups allow traffic?
- [ ] IAM roles attached?
- [ ] Secrets in production match local?

---

## Key Patterns Summary

### Bootstrap Script Structure
```bash
1. Set up logging (critical!)
2. Install system dependencies
3. Configure services
4. Clone application code
5. Create configuration files
6. Wait for dependent resources
7. Initialize application (migrations, database setup)
8. Start application
```

### IAM for Applications
```
Trust Policy (who can use role)
  ↓
IAM Role (identity)
  ↓
Permissions Policy (what role can do)
  ↓
Instance Profile (connector to EC2)
  ↓
EC2 Instance (uses temporary credentials)
```

### Idempotent Operations
```python
# Pattern: Check before create
if not exists(thing):
    create(thing)

# SQL: WHERE NOT EXISTS
# Bash: if [ ! -f file ]; then create file; fi
# Terraform: Built-in (creates only if doesn't exist)
```

### Terraform Workflow
```bash
terraform init      # Download providers, initialize backend
terraform plan      # Preview changes (safe, read-only)
terraform apply     # Create/update infrastructure
terraform destroy   # Delete everything (dangerous!)
terraform output    # Show output values
```

---

## Common Mistakes I Made

### 1. Engine Name: "postgres" vs "postgresql"
```hcl
# WRONG
engine = "postgresql"  # Terraform docs use this

# CORRECT  
engine = "postgres"    # AWS API actually uses this
```
**Lesson:** Test with AWS CLI to verify actual API values.

### 2. Forgetting base64encode()
```hcl
# WRONG
user_data = templatefile("script.sh.tpl", {...})

# CORRECT
user_data = base64encode(templatefile("script.sh.tpl", {...}))
```

### 3. Not Logging User Data Output
Without logging, can't debug bootstrap failures.
```bash
# MUST HAVE at top of script
exec > >(tee /var/log/user-data.log) 2>&1
```

### 4. Assuming RDS is Ready When Created
```hcl
# Terraform says "created" but RDS is still initializing
# User data must wait in a loop
```

### 5. Hardcoding Values in Template
```bash
# WRONG - hardcoded endpoint
DATABASE_URL=postgresql://user:pass@localhost:5432/db

# CORRECT - use template variables
DATABASE_URL=postgresql://${db_username}:${db_password}@${rds_endpoint}:5432/${db_name}
```

---

## Quick Reference

### Essential Commands

```bash
# Terraform
terraform init                 # Initialize (first time)
terraform plan                 # Preview changes
terraform apply                # Apply changes
terraform destroy              # Delete everything
terraform output              # Show outputs
terraform state list          # List resources
terraform state show <resource>  # Show resource details

# EC2 Debugging
ssh -i ~/.ssh/key.pem ec2-user@<IP>
sudo tail -f /var/log/user-data.log
sudo cloud-init status
docker ps
docker logs <container>

# Database Testing
PGPASSWORD='pass' psql -h <endpoint> -U user -d db -c '\dt'

# Redis Testing
redis-cli -h <endpoint> ping
```

### File Locations on EC2

```
/var/log/user-data.log          # Bootstrap script output
/var/log/cloud-init.log         # Cloud-init logs
/var/log/cloud-init-output.log  # Another cloud-init log
/home/ec2-user/task-manager-api # Application code
/home/ec2-user/task-manager-api/.env  # Environment variables
```

---

## Resources

- [AWS User Data Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html)
- [Terraform templatefile() Function](https://www.terraform.io/language/functions/templatefile)
- [IAM Roles for EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html)
- [Docker ENTRYPOINT vs CMD](https://docs.docker.com/engine/reference/builder/#understand-how-cmd-and-entrypoint-interact)
- [PostgreSQL Idempotent Operations](https://www.postgresql.org/docs/current/sql-createdb.html)

---

**Last Updated:** December 2, 2025  
**Week:** 11-12 (Infrastructure as Code - Terraform Deployment)  
**Status:** Complete ✅ - 13 AWS resources automated
