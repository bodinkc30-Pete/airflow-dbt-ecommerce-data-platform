resource "aws_ecs_cluster" "airflow" {
  name = "${local.name}-airflow"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "airflow" {
  for_each = local.airflow_components

  name              = "/project06/${var.environment}/airflow/${each.key}"
  retention_in_days = var.cloudwatch_log_retention_days
}

resource "aws_cloudwatch_log_group" "bootstrap" {
  name              = "/project06/${var.environment}/airflow/bootstrap"
  retention_in_days = var.cloudwatch_log_retention_days
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-airflow-alb"
  description = "HTTPS ingress to Airflow API"
  vpc_id      = aws_vpc.platform.id

  dynamic "ingress" {
    for_each = toset(var.airflow_ingress_cidrs)
    content {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${local.name}-airflow-ecs"
  description = "Airflow ECS task networking"
  vpc_id      = aws_vpc.platform.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "airflow" {
  name               = substr("${local.name}-airflow", 0, 32)
  internal           = var.airflow_alb_internal
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.airflow_alb_internal ? aws_subnet.private[*].id : aws_subnet.public[*].id

  drop_invalid_header_fields = true
  enable_deletion_protection = var.environment == "prod"
}
resource "aws_lb_target_group" "airflow_api" {
  name        = substr("${local.name}-airflow-api", 0, 32)
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.platform.id

  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/api/v2/monitor/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.airflow.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.airflow_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.airflow_api.arn
  }
}

resource "aws_ecs_task_definition" "airflow" {
  for_each = local.airflow_components

  family                   = "${local.name}-airflow-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(each.value.cpu)
  memory                   = tostring(each.value.memory)
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.airflow_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  volume {
    name = "airflow-logs"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.airflow_logs.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.airflow_logs.id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([
    merge({
      name        = "airflow-${each.key}"
      image       = local.airflow_image_uri
      essential   = true
      command     = each.value.command
      environment = local.common_airflow_environment
      secrets     = local.common_airflow_secrets
      mountPoints = [{
        sourceVolume  = "airflow-logs"
        containerPath = "/opt/airflow/logs"
        readOnly      = false
      }]
      linuxParameters = { initProcessEnabled = true }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.airflow[each.key].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      }, jsondecode(each.key == "api" ? jsonencode({
        portMappings = [{
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }]
        healthCheck = {
          command     = ["CMD-SHELL", "curl --fail http://localhost:8080/api/v2/monitor/health || exit 1"]
          interval    = 30
          timeout     = 10
          retries     = 3
          startPeriod = 60
        }
    }) : "{}"))
  ])
}

resource "aws_ecs_service" "airflow" {
  for_each = local.airflow_components

  name            = "${local.name}-airflow-${each.key}"
  cluster         = aws_ecs_cluster.airflow.id
  task_definition = aws_ecs_task_definition.airflow[each.key].arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = each.key == "api" ? 120 : null

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = each.key == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.airflow_api.arn
      container_name   = "airflow-api"
      container_port   = 8080
    }
  }

  depends_on = [
    aws_lb_listener.https,
    aws_efs_mount_target.airflow_logs,
  ]
}

resource "aws_ecs_task_definition" "bootstrap" {
  family                   = "${local.name}-airflow-bootstrap"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.airflow_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "airflow-bootstrap"
    image     = local.airflow_image_uri
    essential = true
    command = [
      "bash",
      "-c",
      "python /opt/airflow/scripts/bootstrap_cloud_database.py && export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/airflow?sslmode=require && airflow db migrate && python /opt/airflow/scripts/bootstrap_fab_admin.py && airflow pools set postgres_ingestion 2 'PostgreSQL ingestion work' && airflow pools set dbt_transform 1 'Serialized dbt transformations'",
    ]
    environment = concat(local.common_airflow_environment, [
      { name = "POSTGRES_SSLMODE", value = "require" },
    ])
    secrets = concat(local.common_airflow_secrets, [
      { name = "RDS_MASTER_USER", valueFrom = "${aws_db_instance.platform.master_user_secret[0].secret_arn}:username::" },
      { name = "RDS_MASTER_PASSWORD", valueFrom = "${aws_db_instance.platform.master_user_secret[0].secret_arn}:password::" },
      { name = "FAB_ADMIN_USERNAME", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:fab_admin_username::" },
      { name = "FAB_ADMIN_PASSWORD", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:fab_admin_password::" },
      { name = "FAB_ADMIN_EMAIL", valueFrom = "${aws_secretsmanager_secret.airflow_runtime.arn}:fab_admin_email::" },
    ])
    linuxParameters = { initProcessEnabled = true }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.bootstrap.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}