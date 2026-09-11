import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARTS_ROOT = REPO_ROOT / "dbt" / "models" / "marts"
MARTS_SCHEMA = MARTS_ROOT / "_marts__models.yml"
WAREHOUSE_ERD = REPO_ROOT / "docs" / "architecture" / "warehouse_erd.md"
AWS_INTEROP = REPO_ROOT / "docs" / "architecture" / "aws_glue_redshift_interoperability.md"

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


def test_warehouse_erd_tracks_marts_relationship_contract() -> None:
    schema_text = MARTS_SCHEMA.read_text(encoding="utf-8")
    current_model = None
    expected_edges: set[tuple[str, str]] = set()
    for line in schema_text.splitlines():
        model_match = re.match(r"^  - name: ([a-z0-9_]+)$", line)
        if model_match:
            current_model = model_match.group(1)
            continue
        target_match = re.search(r"to: ref\('([a-z0-9_]+)'\)", line)
        if target_match and current_model:
            expected_edges.add((target_match.group(1), current_model))

    erd_text = WAREHOUSE_ERD.read_text(encoding="utf-8")
    actual_edges = {
        (left.lower(), right.lower())
        for left, right in re.findall(
            r"^\s+([A-Z_]+)\s+\S+\s+([A-Z_]+)\s+:\s+\"",
            erd_text,
            flags=re.MULTILINE,
        )
    }
    assert expected_edges
    assert actual_edges == expected_edges


def test_redshift_interop_documents_current_postgres_portability_gaps() -> None:
    sql_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (REPO_ROOT / "dbt").rglob("*.sql")
    )
    interop = AWS_INTEROP.read_text(encoding="utf-8")
    expected_tokens = {
        "distinct on (": "`DISTINCT ON (...)`",
        "generate_series": "`generate_series`",
        "pg_input_is_valid": "`pg_input_is_valid`",
        "timestamptz": "`timestamptz`",
    }
    for sql_token, documented_token in expected_tokens.items():
        assert sql_token in sql_text
        assert documented_token in interop

    profile = (REPO_ROOT / "dbt" / "profiles.yml").read_text(encoding="utf-8")
    assert "type: postgres" in profile
    assert "uses the `postgres` adapter" in interop
    assert "does not claim that Glue or Redshift is deployed today" in interop
    assert "a Redshift migration is **not** a profile-\nonly change" in interop
