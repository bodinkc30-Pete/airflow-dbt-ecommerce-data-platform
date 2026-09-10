resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "PostgreSQL access from Airflow ECS tasks"
  vpc_id      = aws_vpc.platform.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "efs" {
  name        = "${local.name}-efs"
  description = "NFS access from Airflow ECS tasks"
  vpc_id      = aws_vpc.platform.id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_db_subnet_group" "platform" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.database[*].id
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${local.name}-postgres17"
  family = "postgres17"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "track_io_timing"
    value = "1"
  }

  parameter {
    name  = "log_lock_waits"
    value = "1"
  }
}

resource "aws_db_instance" "platform" {
  identifier = local.name

  engine         = "postgres"
  engine_version = var.postgres_engine_version
  instance_class = var.rds_instance_class

  allocated_storage           = var.rds_allocated_storage_gb
  max_allocated_storage       = var.rds_allocated_storage_gb * 5
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "ecommerce"
  username                    = "project06_admin"
  manage_master_user_password = true
  port                        = 5432

  db_subnet_group_name   = aws_db_subnet_group.platform.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  parameter_group_name   = aws_db_parameter_group.postgres.name

  multi_az                = var.environment == "prod" ? true : var.rds_multi_az
  backup_retention_period = max(var.rds_backup_retention_days, var.environment == "prod" ? 7 : 1)
  deletion_protection     = var.environment == "prod"
  skip_final_snapshot     = var.environment != "prod"

  final_snapshot_identifier  = var.environment == "prod" ? "${local.name}-final" : null
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
}
