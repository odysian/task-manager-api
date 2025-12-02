resource "aws_elasticache_subnet_group" "default" {
  name       = "${var.project_name}-elasticache-subnet-group"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name = "${var.project_name}-elasticache-subnet-group"
  }
}
resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.project_name}-redis-params"
  family = "redis7"
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-elasticache-cluster"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.micro"
  port                 = 6379
  num_cache_nodes      = 1
  subnet_group_name    = aws_elasticache_subnet_group.default.name
  security_group_ids   = [aws_security_group.redis.id]
  parameter_group_name = aws_elasticache_parameter_group.redis.name

  tags = {
    Name = "${var.project_name}-elasticache"
  }
}
