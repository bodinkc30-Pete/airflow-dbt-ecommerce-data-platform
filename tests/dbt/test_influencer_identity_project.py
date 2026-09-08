from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_ROOT = REPO_ROOT / "dbt"
IDENTITY_ROOT = DBT_ROOT / "models" / "identity"

EXPECTED_IDENTITY_MODELS = {
    "influencer_identity_map.sql",
    "influencer_entities.sql",
    "influencer_identity_review_queue.sql",
}


def test_influencer_identity_models_exist() -> None:
    actual = {path.name for path in IDENTITY_ROOT.glob("*.sql")}
    assert actual == EXPECTED_IDENTITY_MODELS


def test_identity_normalization_macro_exists() -> None:
    macro = DBT_ROOT / "macros" / "normalize_influencer_identity.sql"
    assert macro.is_file()


def test_identity_layer_has_dedicated_schema_config() -> None:
    project = (DBT_ROOT / "dbt_project.yml").read_text(encoding="utf-8")
    assert "+schema: identity" in project

def test_identity_map_uses_versioned_provisional_name_key() -> None:
    sql = (IDENTITY_ROOT / "influencer_identity_map.sql").read_text(encoding="utf-8")
    assert "normalized_name_v1" in sql
    assert "infl_name_v1_" in sql
    assert "identity_confidence" in sql
    assert "provisional" in sql


def test_entity_review_conflicts_are_snapshot_scoped() -> None:
    sql = (IDENTITY_ROOT / "influencer_entities.sql").read_text(encoding="utf-8")
    assert "ingestion_file_id" in sql
    assert "snapshot_groups" in sql
    assert "conflicting_snapshot_count" in sql


def test_review_queue_reads_only_from_entity_registry() -> None:
    sql = (IDENTITY_ROOT / "influencer_identity_review_queue.sql").read_text(
        encoding="utf-8"
    )
    assert "ref('influencer_entities')" in sql
    assert "requires_manual_review" in sql
