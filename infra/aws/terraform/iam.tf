data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "airflow_task" {
  name               = "${local.name}-airflow-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid     = "ReadRuntimeSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = compact([
      aws_secretsmanager_secret.airflow_runtime.arn,
      try(aws_db_instance.platform.master_user_secret[0].secret_arn, null),
    ])
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${local.name}-execution-secrets"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

data "aws_iam_policy_document" "airflow_data" {
  statement {
    sid       = "ListLanding"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.landing.arn]
  }

  statement {
    sid       = "ReadLandingObjects"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.landing.arn}/landing/*"]
  }

  statement {
    sid       = "ListAirflowLogs"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.airflow_logs.arn]
  }

  statement {
    sid = "ReadWriteAirflowLogs"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.airflow_logs.arn}/airflow/*"]
  }
}

resource "aws_iam_role_policy" "airflow_data" {
  name   = "${local.name}-airflow-data"
  role   = aws_iam_role.airflow_task.id
  policy = data.aws_iam_policy_document.airflow_data.json
}
