provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "PROJECT 06"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

locals {
  name              = "${var.project_name}-${var.environment}"
  airflow_image_uri = "${aws_ecr_repository.airflow.repository_url}:${var.airflow_image_tag}"
  azs               = slice(data.aws_availability_zones.available.names, 0, 2)

  public_subnet_cidrs  = [for index in range(2) : cidrsubnet(var.vpc_cidr, 4, index)]
  private_subnet_cidrs = [for index in range(2) : cidrsubnet(var.vpc_cidr, 4, index + 2)]
  db_subnet_cidrs      = [for index in range(2) : cidrsubnet(var.vpc_cidr, 4, index + 4)]

  airflow_components = {
    api = {
      command = ["bash", "-c", "export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/airflow?sslmode=require; exec airflow api-server"]
      cpu     = 512
      memory  = 1024
      port    = 8080
    }
    scheduler = {
      command = ["bash", "-c", "export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/airflow?sslmode=require; exec airflow scheduler"]
      cpu     = 1024
      memory  = 2048
      port    = null
    }
    dag_processor = {
      command = ["bash", "-c", "export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/airflow?sslmode=require; exec airflow dag-processor"]
      cpu     = 512
      memory  = 1024
      port    = null
    }
    triggerer = {
      command = ["bash", "-c", "export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/airflow?sslmode=require; exec airflow triggerer"]
      cpu     = 512
      memory  = 1024
      port    = null
    }
  }

  common_airflow_environment = [
    { name = "PYTHONPATH", value = "/opt/airflow/src" },
    { name = "AIRFLOW__CORE__EXECUTOR", value = "LocalExecutor" },
    { name = "AIRFLOW__CORE__LOAD_EXAMPLES", value = "False" },
    { name = "AIRFLOW__CORE__AUTH_MANAGER", value = "airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager" },
    { name = "AIRFLOW__DATABASE__EXTERNAL_DB_MANAGERS", value = "airflow.providers.fab.auth_manager.models.db.FABDBManager" },
    { name = "AIRFLOW__API__BASE_URL", value = "https://${var.airflow_domain_name}" },
    { name = "AIRFLOW__LOGGING__REMOTE_LOGGING", value = "True" },
    { name = "AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER", value = "s3://${aws_s3_bucket.airflow_logs.bucket}/airflow" },
    { name = "AIRFLOW_CONN_AWS_DEFAULT", value = "aws://" },
    { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    { name = "DATA_MODE", value = "s3" },
    { name = "S3_DATA_BUCKET", value = aws_s3_bucket.landing.bucket },
    { name = "S3_DATA_PREFIX", value = "landing" },
    { name = "DATA_CLOUD_STAGING_DIR", value = "/opt/airflow/data/cloud" },
    { name = "POSTGRES_HOST", value = aws_db_instance.platform.address },
    { name = "POSTGRES_PORT", value = "5432" },
    { name = "POSTGRES_DB", value = "ecommerce" },
    { name = "POSTGRES_ROLE", value = "ecommerce_ingest_writer" },
    { name = "DBT_PROFILES_DIR", value = "/opt/airflow/dbt" },
    { name = "DBT_PROJECT_DIR", value = "/opt/airflow/dbt" },
    { name = "DBT_TARGET", value = "dev" },
    { name = "DBT_POSTGRES_HOST", value = aws_db_instance.platform.address },
    { name = "DBT_POSTGRES_PORT", value = "5432" },
    { name = "DBT_POSTGRES_DB", value = "ecommerce" },
    { name = "DBT_POSTGRES_ROLE", value = "ecommerce_transformer" },
    { name = "DBT_POSTGRES_SSLMODE", value = "require" },
    { name = "DBT_SCHEMA", value = "analytics" },
    { name = "DBT_THREADS", value = "2" },
  ]

  common_airflow_secrets = [
    { name = "POSTGRES_USER", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:postgres_user::" },
    { name = "POSTGRES_PASSWORD", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:postgres_password::" },
    { name = "DBT_POSTGRES_USER", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:postgres_user::" },
    { name = "DBT_POSTGRES_PASSWORD", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:postgres_password::" },
    { name = "AIRFLOW__API_AUTH__JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:airflow_jwt_secret::" },
    { name = "AIRFLOW__API__SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:airflow_api_secret_key::" },
    { name = "AIRFLOW__CORE__FERNET_KEY", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:airflow_fernet_key::" },
  ]
}