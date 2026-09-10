variable "project_name" {
  type        = string
  description = "Lowercase project slug used in AWS resource names."
  default     = "project06"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase letters, digits, and hyphens."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region for the platform."
  default     = "ap-southeast-1"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR for the Project 06 VPC."
  default     = "10.42.0.0/16"
}

variable "airflow_image_tag" {
  type        = string
  description = "Immutable tag pushed to the Terraform-managed ECR repository."
  default     = "part17"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", var.airflow_image_tag))
    error_message = "airflow_image_tag must be a valid non-empty container image tag."
  }
}

variable "airflow_domain_name" {
  type        = string
  description = "DNS name served by the Airflow HTTPS endpoint."
}

variable "airflow_certificate_arn" {
  type        = string
  description = "ACM certificate ARN for the Airflow HTTPS listener."
}

variable "airflow_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the Airflow ALB. Keep restricted in production."
  default     = []
}

variable "airflow_alb_internal" {
  type        = bool
  description = "Create an internal ALB by default."
  default     = true
}

variable "airflow_runtime_secret_json" {
  type        = string
  sensitive   = true
  ephemeral   = true
  description = "JSON secret containing PostgreSQL, Airflow runtime, and initial FAB admin credentials."

  validation {
    condition = alltrue([
      can(jsondecode(var.airflow_runtime_secret_json).postgres_user),
      can(jsondecode(var.airflow_runtime_secret_json).postgres_password),
      can(jsondecode(var.airflow_runtime_secret_json).airflow_jwt_secret),
      can(jsondecode(var.airflow_runtime_secret_json).airflow_api_secret_key),
      can(jsondecode(var.airflow_runtime_secret_json).airflow_fernet_key),
      can(jsondecode(var.airflow_runtime_secret_json).fab_admin_username),
      can(jsondecode(var.airflow_runtime_secret_json).fab_admin_password),
      can(jsondecode(var.airflow_runtime_secret_json).fab_admin_email),
    ])
    error_message = "airflow_runtime_secret_json is missing one or more required keys."
  }
}

variable "airflow_runtime_secret_version" {
  type        = number
  description = "Monotonic trigger for rotating the write-only Airflow runtime secret."
  default     = 1

  validation {
    condition     = var.airflow_runtime_secret_version >= 1 && floor(var.airflow_runtime_secret_version) == var.airflow_runtime_secret_version
    error_message = "airflow_runtime_secret_version must be a positive integer."
  }
}
variable "postgres_engine_version" {
  type        = string
  description = "RDS PostgreSQL engine version."
  default     = "17.10"
}

variable "rds_instance_class" {
  type        = string
  description = "RDS instance class for the reference deployment."
  default     = "db.t4g.micro"
}

variable "rds_allocated_storage_gb" {
  type        = number
  description = "Initial gp3 storage for RDS."
  default     = 20
}

variable "rds_backup_retention_days" {
  type        = number
  description = "Automated backup retention."
  default     = 7
}

variable "rds_multi_az" {
  type        = bool
  description = "Enable Multi-AZ outside the enforced production default."
  default     = false
}

variable "ecs_desired_count" {
  type        = number
  description = "Desired count per Airflow ECS service after database bootstrap. LocalExecutor keeps this at 0 or 1."
  default     = 0

  validation {
    condition     = var.ecs_desired_count >= 0 && var.ecs_desired_count <= 1 && floor(var.ecs_desired_count) == var.ecs_desired_count
    error_message = "ecs_desired_count must be 0 or 1 while Part 17 uses LocalExecutor."
  }
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Enable NAT egress for external integrations such as outbound webhooks."
  default     = false
}

variable "cloudwatch_log_retention_days" {
  type        = number
  description = "Operational CloudWatch container-log retention."
  default     = 30
}