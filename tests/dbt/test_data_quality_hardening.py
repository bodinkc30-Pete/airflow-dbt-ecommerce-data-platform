from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBT = ROOT / "dbt"


def test_part8_quality_assets_exist() -> None:
    assert (DBT / "macros" / "tests" / "non_negative.sql").exists()
    assert (DBT / "macros" / "tests" / "value_between.sql").exists()
    assert (DBT / "macros" / "tests" / "timestamp_not_before.sql").exists()
    assert (DBT / "selectors.yml").exists()


def test_sources_define_loaded_at_freshness() -> None:
    text = (DBT / "models" / "staging" / "_staging__sources.yml").read_text(encoding="utf-8")
    assert text.count("loaded_at_field") >= 8
    assert text.count("warn_after") >= 8


def test_quality_policy_document_exists() -> None:
    assert (ROOT / "docs" / "architecture" / "dbt_data_quality_part8.md").exists()