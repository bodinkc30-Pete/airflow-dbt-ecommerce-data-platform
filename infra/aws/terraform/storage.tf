resource "aws_ecr_repository" "airflow" {
  name                 = "${local.name}-airflow"
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_s3_bucket" "landing" {
  bucket = "${local.name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}-landing"
}

resource "aws_s3_bucket" "airflow_logs" {
  bucket = "${local.name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}-airflow-logs"
}

resource "aws_s3_bucket_public_access_block" "landing" {
  bucket                  = aws_s3_bucket.landing.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_public_access_block" "airflow_logs" {
  bucket                  = aws_s3_bucket.airflow_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "airflow_logs" {
  bucket = aws_s3_bucket.airflow_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_versioning" "landing" {
  bucket = aws_s3_bucket.landing.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "airflow_logs" {
  bucket = aws_s3_bucket.airflow_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_efs_file_system" "airflow_logs" {
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"
  tags             = { Name = "${local.name}-airflow-logs" }
}

resource "aws_efs_access_point" "airflow_logs" {
  file_system_id = aws_efs_file_system.airflow_logs.id

  posix_user {
    uid = 50000
    gid = 0
  }
  root_directory {
    path = "/airflow-logs"
    creation_info {
      owner_uid   = 50000
      owner_gid   = 0
      permissions = "0770"
    }
  }
}

resource "aws_efs_mount_target" "airflow_logs" {
  count           = 2
  file_system_id  = aws_efs_file_system.airflow_logs.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_secretsmanager_secret" "airflow_runtime" {
  name                    = "${local.name}/airflow-runtime"
  recovery_window_in_days = var.environment == "prod" ? 30 : 7
}

resource "aws_secretsmanager_secret_version" "airflow_runtime" {
  secret_id                = aws_secretsmanager_secret.airflow_runtime.id
  secret_string_wo         = var.airflow_runtime_secret_json
  secret_string_wo_version = var.airflow_runtime_secret_version
}