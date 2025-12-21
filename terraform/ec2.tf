resource "aws_instance" "api" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro"
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  key_name                    = var.key_name
  associate_public_ip_address = true
  subnet_id                   = data.aws_subnets.default.ids[0]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  user_data_replace_on_change = true
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
    sns_topic_arn         = aws_sns_topic.notifications.arn
    backend_domain        = var.backend_domain
    frontend_domain       = var.frontend_domain
    ssl_email             = var.ssl_email
  }))

  tags = {
    Name = "${var.project_name}-ec2"
  }

  # Wait fro RDS and Redis before launching EC2
  depends_on = [
    aws_db_instance.postgres,
    aws_elasticache_cluster.redis
  ]
}

# Trust policy - allows EC2 service to assume this role
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

# Create IAM role
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

# Permission policy
data "aws_iam_policy_document" "ec2_s3_access" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::${var.s3_bucket_name}/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sns:Publish",
      "sns:Subscribe",
      "sns:Unsubscribe",
      "sns:ListSubscriptionsByTopic"
    ]
    resources = ["arn:aws:sns:${var.aws_region}:*:task-manager-notifications"]
  }
}

resource "aws_iam_policy" "ec2_s3_policy" {
  name   = "${var.project_name}-ec2-s3-policy"
  policy = data.aws_iam_policy_document.ec2_s3_access.json
}

resource "aws_iam_role_policy_attachment" "ec2_s3_attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_s3_policy.arn
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

data "aws_eip" "static" {
  filter {
    name   = "tag:Name"
    values = ["task-manager-static-ip"]
  }
}

resource "aws_eip_association" "api" {
  instance_id   = aws_instance.api.id
  allocation_id = data.aws_eip.static.id
}
