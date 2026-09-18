from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import psycopg2
from psycopg2.extensions import connection as PgConnection


@dataclass(frozen=True)
class ConnectionSummary:
    total: int
    active: int
    idle_in_transaction: int
    waiting: int
    max_connections: int
    usage_percent: float


@dataclass(frozen=True)
class BlockingSession:
    blocked_pid: int
    blocker_pid: int
    blocked_seconds: float


@dataclass(frozen=True)
class LongRunningSession:
    pid: int
    state: str
    wait_event_type: str | None
    wait_event: str | None
    duration_seconds: float


@dataclass(frozen=True)
class QueryStat:
    query_id: int
    calls: int
    total_exec_time_ms: float
    mean_exec_time_ms: float
    rows: int


@dataclass(frozen=True)
class PostgresDependencyProbe:
    available: bool
    category: str
    error_type: str | None
    database: str | None
    server_version: str | None


@dataclass(frozen=True)
class PostgresDiagnostics:
    captured_at: datetime
    database: str
    server_version: str
    connections: ConnectionSummary
    blocking_sessions: tuple[BlockingSession, ...]
    long_running_sessions: tuple[LongRunningSession, ...]
    top_queries: tuple[QueryStat, ...]


def _load_metadata(connection: PgConnection) -> tuple[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_setting('server_version');")
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("PostgreSQL metadata query returned no row")
    return str(row[0]), str(row[1])


def _load_connections(connection: PgConnection) -> ConnectionSummary:
    query = """
        SELECT
            COUNT(*) FILTER (WHERE datname = current_database()),
            COUNT(*) FILTER (
                WHERE datname = current_database() AND state = 'active'
            ),
            COUNT(*) FILTER (
                WHERE datname = current_database() AND state = 'idle in transaction'
            ),
            COUNT(*) FILTER (
                WHERE datname = current_database() AND wait_event IS NOT NULL
            ),
            current_setting('max_connections')::integer
        FROM pg_stat_activity;
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("PostgreSQL connection summary returned no row")

    total = int(row[0])
    max_connections = int(row[4])
    usage_percent = 0.0 if max_connections <= 0 else round(total * 100 / max_connections, 2)
    return ConnectionSummary(
        total=total,
        active=int(row[1]),
        idle_in_transaction=int(row[2]),
        waiting=int(row[3]),
        max_connections=max_connections,
        usage_percent=usage_percent,
    )


def _load_blocking_sessions(connection: PgConnection) -> tuple[BlockingSession, ...]:
    query = """
        SELECT
            blocked.pid,
            blocker_pid,
            EXTRACT(EPOCH FROM (clock_timestamp() - blocked.query_start))::double precision
        FROM pg_stat_activity AS blocked
        CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS blocker_pid
        WHERE blocked.datname = current_database()
        ORDER BY blocked.query_start;
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return tuple(
        BlockingSession(
            blocked_pid=int(row[0]),
            blocker_pid=int(row[1]),
            blocked_seconds=max(0.0, float(row[2] or 0.0)),
        )
        for row in rows
    )


def _load_long_running_sessions(
    connection: PgConnection,
    *,
    threshold_seconds: int,
) -> tuple[LongRunningSession, ...]:
    query = """
        /* long_running */
        SELECT pid, state, wait_event_type, wait_event,
               EXTRACT(EPOCH FROM (
                   clock_timestamp() - COALESCE(xact_start, query_start)
               ))::double precision
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND pid <> pg_backend_pid()
          AND state <> 'idle'
          AND clock_timestamp() - COALESCE(xact_start, query_start)
              >= (%s * interval '1 second')
        ORDER BY COALESCE(xact_start, query_start);
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (threshold_seconds,))
        rows = cursor.fetchall()
    return tuple(
        LongRunningSession(
            pid=int(row[0]),
            state=str(row[1]),
            wait_event_type=str(row[2]) if row[2] is not None else None,
            wait_event=str(row[3]) if row[3] is not None else None,
            duration_seconds=max(0.0, float(row[4] or 0.0)),
        )
        for row in rows
    )


def _load_top_queries(connection: PgConnection, *, limit: int) -> tuple[QueryStat, ...]:
    query = """
        SELECT queryid, calls, total_exec_time, mean_exec_time, rows
        FROM pg_stat_statements
        WHERE dbid = (
            SELECT oid FROM pg_database WHERE datname = current_database()
        )
        ORDER BY total_exec_time DESC, queryid
        LIMIT %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
    return tuple(
        QueryStat(
            query_id=int(row[0]),
            calls=int(row[1]),
            total_exec_time_ms=float(row[2]),
            mean_exec_time_ms=float(row[3]),
            rows=int(row[4]),
        )
        for row in rows
    )


def load_postgres_diagnostics(
    connection: PgConnection,
    *,
    long_running_threshold_seconds: int = 60,
    top_query_limit: int = 10,
    captured_at: datetime | None = None,
) -> PostgresDiagnostics:
    if long_running_threshold_seconds <= 0:
        raise ValueError("long_running_threshold_seconds must be > 0")
    if top_query_limit <= 0:
        raise ValueError("top_query_limit must be > 0")

    database, server_version = _load_metadata(connection)
    return PostgresDiagnostics(
        captured_at=captured_at or datetime.now(UTC),
        database=database,
        server_version=server_version,
        connections=_load_connections(connection),
        blocking_sessions=_load_blocking_sessions(connection),
        long_running_sessions=_load_long_running_sessions(
            connection,
            threshold_seconds=long_running_threshold_seconds,
        ),
        top_queries=_load_top_queries(connection, limit=top_query_limit),
    )


def diagnostics_to_dict(diagnostics: PostgresDiagnostics) -> dict[str, object]:
    payload = asdict(diagnostics)
    payload["captured_at"] = diagnostics.captured_at.isoformat()
    return payload


def probe_postgres_dependency(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    connect_timeout_seconds: int = 1,
) -> PostgresDependencyProbe:
    try:
        connection = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password,
            connect_timeout=connect_timeout_seconds,
        )
    except psycopg2.OperationalError as exc:
        return PostgresDependencyProbe(
            available=False,
            category='database_unavailable',
            error_type=type(exc).__name__,
            database=None,
            server_version=None,
        )

    try:
        database_name, server_version = _load_metadata(connection)
    finally:
        connection.close()

    return PostgresDependencyProbe(
        available=True,
        category='healthy',
        error_type=None,
        database=database_name,
        server_version=server_version,
    )
