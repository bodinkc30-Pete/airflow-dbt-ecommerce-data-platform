from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARTS_ROOT = REPO_ROOT / "dbt" / "models" / "marts"

EXPECTED_MODELS = {
    "dim_date.sql", "dim_product.sql", "dim_sku.sql", "dim_influencer.sql",
    "fact_order_items.sql", "fact_orders.sql", "fact_shop_daily.sql", "fact_campaign_daily.sql",
    "fact_live_daily.sql", "fact_product_card_daily.sql",
    "fact_influencer_observation.sql",
}


def test_star_schema_models_exist() -> None:
    actual = {p.name for p in MARTS_ROOT.glob("*.sql")}
    assert actual == EXPECTED_MODELS


def test_marts_are_materialized_as_tables() -> None:
    project = (REPO_ROOT / "dbt" / "dbt_project.yml").read_text(encoding="utf-8")
    assert "marts:" in project
    assert "+materialized: table" in project


def test_order_fact_uses_unknown_members() -> None:
    sql = (MARTS_ROOT / "fact_order_items.sql").read_text(encoding="utf-8")
    assert "sku_unknown" in sql
    assert "product_unknown" in sql
    assert "influencer_unknown" in sql
    assert "coalesce" in sql.lower()



def test_order_item_fact_excludes_order_level_measures() -> None:
    sql = (MARTS_ROOT / "fact_order_items.sql").read_text(encoding="utf-8")
    forbidden = {
        "order_amount",
        "shipping_fee_after_discount",
        "original_shipping_fee",
        "payment_platform_discount",
        "taxes",
    }
    for column_name in forbidden:
        assert column_name not in sql


def test_order_fact_contains_order_level_amount() -> None:
    sql = (MARTS_ROOT / "fact_orders.sql").read_text(encoding="utf-8")
    assert "latest.order_amount" in sql
    assert "sku_line_count" in sql
