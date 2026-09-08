from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERMEDIATE_ROOT = REPO_ROOT / "dbt" / "models" / "intermediate"

EXPECTED_MODELS = {
    "int_products_current.sql",
    "int_skus_current.sql",
    "int_product_sku_catalog.sql",
    "int_order_items_current.sql",
    "int_creator_identity_bridge.sql",
    "int_order_items_enriched.sql",
    "int_shop_daily_current.sql",
    "int_campaign_daily_current.sql",
    "int_live_daily_current.sql",
    "int_product_card_daily_current.sql",
    "int_daily_performance.sql",
}


def test_intermediate_models_exist() -> None:
    actual = {path.name for path in INTERMEDIATE_ROOT.glob("int_*.sql")}
    assert actual == EXPECTED_MODELS


def test_intermediate_project_config_exists() -> None:
    project = (REPO_ROOT / "dbt" / "dbt_project.yml").read_text(encoding="utf-8")
    assert "intermediate:" in project
    assert "+schema: intermediate" in project


def test_order_enrichment_is_row_preserving() -> None:
    sql = (INTERMEDIATE_ROOT / "int_order_items_enriched.sql").read_text(encoding="utf-8")
    lowered = sql.lower()
    assert "left join" in lowered
    assert "inner join" not in lowered
    assert "int_product_sku_catalog" in sql
    assert "int_creator_identity_bridge" in sql
