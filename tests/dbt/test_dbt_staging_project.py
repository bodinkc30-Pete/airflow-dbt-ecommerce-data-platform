from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_ROOT = REPO_ROOT / "dbt"
STAGING_ROOT = DBT_ROOT / "models" / "staging"

EXPECTED_MODELS = {
    "stg_orders.sql",
    "stg_products.sql",
    "stg_skus.sql",
    "stg_shop_analytics.sql",
    "stg_campaign.sql",
    "stg_live.sql",
    "stg_product_card.sql",
    "stg_influencer.sql",
}

FORBIDDEN_ORDER_COLUMNS = {
    "buyer_message",
    "buyer_username",
    "recipient",
    "phone_number",
    "detail_address",
    "tax_info_buyer_tax_id",
    "tax_info_email",
    "tax_info_phone_number",
}


def test_dbt_project_files_exist() -> None:
    assert (DBT_ROOT / "dbt_project.yml").is_file()
    assert (DBT_ROOT / "profiles.yml").is_file()
    assert (STAGING_ROOT / "_staging__sources.yml").is_file()
    assert (STAGING_ROOT / "_staging__models.yml").is_file()


def test_expected_staging_models_exist() -> None:
    actual_models = {path.name for path in STAGING_ROOT.glob("stg_*.sql")}
    assert actual_models == EXPECTED_MODELS


def test_orders_staging_excludes_private_columns() -> None:
    sql = (STAGING_ROOT / "stg_orders.sql").read_text(encoding="utf-8")
    for column_name in FORBIDDEN_ORDER_COLUMNS:
        assert column_name not in sql


def test_profiles_use_environment_variables() -> None:
    profile = (DBT_ROOT / "profiles.yml").read_text(encoding="utf-8")
    assert "DBT_POSTGRES_HOST" in profile
    assert "DBT_POSTGRES_PASSWORD" in profile
    assert "localhost" in profile
