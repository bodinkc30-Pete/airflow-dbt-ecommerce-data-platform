-- Project 06: read-only PostgreSQL production diagnostics.
-- Intended for operator triage in psql; every statement is observational.

-- Database identity and server version.
SELECT
    current_database() AS database_name,
    current_setting('server_version') AS server_version;

-- Connection pressure and wait-state summary.
SELECT
    COUNT(*) FILTER (WHERE datname = current_database()) AS total_connections,
    COUNT(*) FILTER (
        WHERE datname = current_database() AND state = 'active'
    ) AS active_connections,
    COUNT(*) FILTER (
        WHERE datname = current_database() AND state = 'idle in transaction'
    ) AS idle_in_transaction,
    COUNT(*) FILTER (
        WHERE datname = current_database() AND wait_event IS NOT NULL
    ) AS waiting_connections,
    current_setting('max_connections')::integer AS max_connections
FROM pg_stat_activity;

-- Sessions blocked by another backend.
SELECT
    blocked.pid AS blocked_pid,
    blocker.blocker_pid,
    ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - blocked.query_start))::numeric, 3)
        AS blocked_seconds,
    blocked.wait_event_type,
    blocked.wait_event
FROM pg_stat_activity AS blocked
CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS blocker(blocker_pid)
WHERE blocked.datname = current_database()
ORDER BY blocked_seconds DESC;

-- Long-running transactions or active statements over 60 seconds.
SELECT
    pid,
    state,
    wait_event_type,
    wait_event,
    ROUND(EXTRACT(EPOCH FROM (
        CURRENT_TIMESTAMP - COALESCE(xact_start, query_start)
    ))::numeric, 3) AS long_running_seconds
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND COALESCE(xact_start, query_start) IS NOT NULL
  AND CURRENT_TIMESTAMP - COALESCE(xact_start, query_start) > INTERVAL '60 seconds'
ORDER BY long_running_seconds DESC;

-- Highest cumulative execution-time query fingerprints.
SELECT
    queryid,
    calls,
    ROUND(total_exec_time::numeric, 3) AS total_exec_time_ms,
    ROUND(mean_exec_time::numeric, 3) AS mean_exec_time_ms,
    rows
FROM pg_stat_statements
WHERE dbid = (
    SELECT oid
    FROM pg_database
    WHERE datname = current_database()
)
ORDER BY total_exec_time DESC
LIMIT 10;
