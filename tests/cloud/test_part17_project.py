from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
DAG = ROOT / "airflow" / "dags" / "ecommerce_ingestion.py"
CLOUD = ROOT / "src" / "ecommerce_pipeline" / "cloud" / "s3_landing.py"
TF = ROOT / "infra" / "aws" / "terraform"


def _terraform_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in TF.glob("*.tf"))


def _compact_terraform_text() -> str:
    return " ".join(_terraform_text().split())


def test_release_image_is_self_contained_without_data() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    for source in ("src", "airflow/dags", "dbt", "scripts"):
        assert f"COPY --chown=airflow:root {source}" in text
    assert "COPY data" not in text


def test_s3_landing_adapter_uses_iam_default_credentials() -> None:
    assert CLOUD.exists()
    text = CLOUD.read_text(encoding="utf-8")
    assert 'boto3.client("s3")' in text
    assert "aws_access_key_id" not in text
    assert "aws_secret_access_key" not in text
    assert "download_file" in text


def test_airflow_supports_s3_data_mode_without_new_task_graph() -> None:
    text = DAG.read_text(encoding="utf-8")
    assert 'data_mode == "s3"' in text
    assert "S3_DATA_BUCKET" in text
    assert "sync_s3_landing" in text
    assert text.count("@task") + text.count("@setup") + text.count("@teardown") == 13


def test_terraform_aws_reference_stack_exists() -> None:
    for name in ("versions.tf", "variables.tf", "main.tf", "outputs.tf"):
        assert (TF / name).exists()
    text = "\n".join(p.read_text(encoding="utf-8") for p in TF.glob("*.tf"))
    for token in (
        "aws_ecs_cluster",
        "aws_ecs_task_definition",
        "aws_db_instance",
        "aws_s3_bucket",
        "aws_secretsmanager_secret",
        "aws_cloudwatch_log_group",
        "aws_efs_file_system",
    ):
        assert token in text


def test_cloud_security_contract_is_explicit() -> None:
    text = _compact_terraform_text()
    assert "publicly_accessible = false" in text
    assert "aws_s3_bucket_public_access_block" in text
    assert "storage_encrypted" in text
    assert "assign_public_ip = false" in text
    assert "SimpleAuthManager" not in text
    assert "FabAuthManager" in text


def test_terraform_provider_and_state_contract_are_pinned() -> None:
    versions = (TF / "versions.tf").read_text(encoding="utf-8")
    assert 'version = "6.62.0"' in versions
    assert 'backend "s3"' in versions
    assert "use_lockfile" in (TF / "backend.hcl.example").read_text(encoding="utf-8")


def test_part17_documentation_exists() -> None:
    assert (ROOT / "docs" / "architecture" / "cloud_infrastructure_part17.md").exists()
    assert (ROOT / "docs" / "evidence" / "cloud_infrastructure_part17_20260910.md").exists()
    assert (ROOT / "docs" / "runbooks" / "cloud_deployment_runbook.md").exists()


def test_cloud_bootstrap_reuses_existing_schema_contract_without_seed() -> None:
    bootstrap = ROOT / "scripts" / "bootstrap_cloud_database.py"
    text = bootstrap.read_text(encoding="utf-8")
    assert 'SCHEMA_DIR = ROOT / "database" / "schema"' in text
    assert "connection.autocommit = True" in text
    assert 'user != "airflow"' in text
    assert "seed_synthetic" not in text
    assert "data/private" not in text


def test_terraform_private_fargate_runtime_guards_are_explicit() -> None:
    text = _compact_terraform_text()
    for token in (
        'target_type = "ip"',
        "deployment_circuit_breaker",
        'transit_encryption = "ENABLED"',
        'service_name = "com.amazonaws.${var.aws_region}.s3"',
        'toset(["ecr.api", "ecr.dkr", "logs", "secretsmanager"])',
    ):
        assert token in text


def test_terraform_secrets_do_not_require_plaintext_state_values() -> None:
    text = "\n".join(p.read_text(encoding="utf-8") for p in TF.glob("*.tf"))
    assert "secret_string_wo" in text
    assert "manage_master_user_password = true" in text
    assert "secret_string = var.airflow_runtime_secret_json" not in text


def test_fab_admin_bootstrap_is_secret_scoped_and_idempotent() -> None:
    ecs = (TF / "ecs.tf").read_text(encoding="utf-8")
    variables = (TF / "variables.tf").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts" / "bootstrap_fab_admin.py").read_text(
        encoding="utf-8"
    )

    assert "bootstrap_fab_admin.py" in ecs
    for name in ("FAB_ADMIN_USERNAME", "FAB_ADMIN_PASSWORD", "FAB_ADMIN_EMAIL"):
        assert name in ecs
    assert "fab_admin_password" in variables
    assert '"users", "list", "--output", "json"' in bootstrap
    assert '"users",\n        "create"' in bootstrap
    assert "SimpleAuthManager" not in ecs


def test_part17_zero_cost_closure_preserves_live_runtime_boundary() -> None:
    runbook = (ROOT / "docs" / "runbooks" / "cloud_deployment_runbook.md").read_text(
        encoding="utf-8"
    )
    evidence = (ROOT / "docs" / "evidence" / "cloud_infrastructure_part17_20260910.md").read_text(
        encoding="utf-8"
    )
    assert "Zero-cost/control-plane closure" in runbook
    assert "no `terraform apply`" in runbook
    assert "live runtime not deployed" in evidence
    assert "70 to add, 0 to change, 0 to destroy" in evidence
