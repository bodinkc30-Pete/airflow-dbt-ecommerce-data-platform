output "ecr_repository_url" {
  description = "ECR repository used for the self-contained Airflow image."
  value       = aws_ecr_repository.airflow.repository_url
}

output "airflow_url" {
  description = "Configured Airflow HTTPS URL."
  value       = "https://${var.airflow_domain_name}"
}

output "airflow_alb_dns_name" {
  description = "ALB DNS name used by DNS after deployment."
  value       = aws_lb.airflow.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster hosting the Airflow control-plane services."
  value       = aws_ecs_cluster.airflow.name
}

output "bootstrap_task_definition_arn" {
  description = "One-off task definition used to bootstrap PostgreSQL and Airflow metadata."
  value       = aws_ecs_task_definition.bootstrap.arn
}

output "landing_bucket_name" {
  description = "Private S3 landing bucket consumed by the S3 adapter."
  value       = aws_s3_bucket.landing.bucket
}

output "airflow_log_bucket_name" {
  description = "Private S3 bucket used for durable Airflow task logs."
  value       = aws_s3_bucket.airflow_logs.bucket
}

output "rds_endpoint" {
  description = "Private PostgreSQL endpoint."
  value       = aws_db_instance.platform.address
}

output "private_subnet_ids" {
  description = "Private ECS subnet IDs."
  value       = aws_subnet.private[*].id
}

output "ecs_security_group_id" {
  description = "Security group used by Airflow ECS tasks and the bootstrap task."
  value       = aws_security_group.ecs.id
}
