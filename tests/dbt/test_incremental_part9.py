from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBT = ROOT / "dbt"
MARTS = DBT / "models" / "marts"

INCREMENTAL_FACTS = {
    "fact_orders.sql": "order_key",
    "fact_order_items.sql": "order_item_key",
    "fact_shop_daily.sql": "date_key",
    "fact_campaign_daily.sql": "date_key",
    "fact_live_daily.sql": "date_key",
    "fact_product_card_daily.sql": "date_key",
    "fact_influencer_observation.sql": "influencer_observation_key",
}

DIMENSIONS = {
    "dim_date.sql",
    "dim_product.sql",
    "dim_sku.sql",
    "dim_influencer.sql",
}


def test_incremental_watermark_macro_exists() -> None:
    text = (DBT / "macros" / "incremental_window_predicate.sql").read_text(
        encoding="utf-8"
    )
    assert "is_incremental()" in text
    assert "backfill_start and backfill_end must be provided together" in text


def test_operational_facts_are_incremental() -> None:
    for filename, unique_key in INCREMENTAL_FACTS.items():
        text = (MARTS / filename).read_text(encoding="utf-8")
        assert "materialized='incremental'" in text
        assert f"unique_key='{unique_key}'" in text
        assert "incremental_strategy='delete+insert'" in text
        assert "on_schema_change='fail'" in text
        assert "incremental_window_predicate" in text


def test_dimensions_remain_rebuild_tables() -> None:
    for filename in DIMENSIONS:
        text = (MARTS / filename).read_text(encoding="utf-8")
        assert "materialized='incremental'" not in text


def test_incremental_selector_and_default_lookback_exist() -> None:
    selectors = (DBT / "selectors.yml").read_text(encoding="utf-8")
    project = (DBT / "dbt_project.yml").read_text(encoding="utf-8")
    assert "name: incremental_facts" in selectors
    assert "method: config.materialized" in selectors
    assert "incremental_lookback_hours: 24" in project


def test_part9_contract_document_exists() -> None:
    assert (ROOT / "docs" / "architecture" / "incremental_processing_part9.md").exists()
