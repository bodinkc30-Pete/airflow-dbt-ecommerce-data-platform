from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql" / "operations" / "postgres_diagnostics.sql"


def test_operator_sql_is_read_only_and_covers_core_diagnostics() -> None:
    text = SQL.read_text(encoding="utf-8")

    for token in (
        "pg_stat_activity",
        "pg_blocking_pids",
        "pg_stat_statements",
        "max_connections",
    ):
        assert token in text

    upper = text.upper()
    for mutating_keyword in (
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "TRUNCATE ",
        "ALTER ",
        "DROP ",
        "CREATE ",
        "CALL ",
    ):
        assert mutating_keyword not in upper
