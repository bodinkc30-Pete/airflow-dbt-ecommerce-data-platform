import os
from datetime import timedelta

import pendulum
from airflow.sdk import DAG, get_current_context, setup, task, teardown
from airflow.task.trigger_rule import TriggerRule
from airflow.timetables.interval import CronDataIntervalTimetable

from ecommerce_pipeline.ingestion.audit_lifecycle import (
    mark_file_failed,
    mark_file_processing,
    mark_file_success,
)
from ecommerce_pipeline.ingestion.bulk_loader import LineageMetadata, bulk_load_source
from ecommerce_pipeline.ingestion.data_quality import (
    evaluate_source_quality,
    has_blocking_quality_failures,
    record_data_quality_results,
)
from ecommerce_pipeline.ingestion.extraction_adapters import extract_source_file
from ecommerce_pipeline.ingestion.file_discovery import discover_all_sources
from ecommerce_pipeline.ingestion.file_registry import (
    build_file_metadata,
    connect_postgres,
    register_file,
)
from ecommerce_pipeline.ingestion.idempotency import decide_file_processing
from ecommerce_pipeline.ingestion.load_contracts import (
    get_load_contract,
    list_load_contract_names,
)
from ecommerce_pipeline.ingestion.run_lifecycle import (
    create_ingestion_run,
    mark_run_failed,
    mark_run_success,
)
from ecommerce_pipeline.ingestion.schema_drift import (
    classify_schema_drift,
    record_schema_events,
)
from ecommerce_pipeline.ingestion.schema_validation import validate_schema
from ecommerce_pipeline.ingestion.source_registry import list_source_names
from ecommerce_pipeline.ingestion.transaction import transaction_scope
from ecommerce_pipeline.monitoring.pipeline_monitoring import (
    build_pipeline_alerts,
    build_pipeline_snapshot,
    load_ingestion_telemetry,
    record_pipeline_alerts,
    record_pipeline_monitoring_run,
    send_webhook_alert,
    update_alert_delivery,
)
from ecommerce_pipeline.orchestration.dbt_runner import (
    DbtCommandError,
    parse_dbt_command_summary,
    resolve_backfill_vars,
    run_dbt_command,
)

_WORK_TASK_IDS = (
    "validate_ingestion_runtime",
    "discover_demo_source_files",
    "register_discovered_files",
    "extract_and_validate_registered_files",
)
_SUPPORTED_AIRFLOW_RUN_TYPES = {"manual", "scheduled", "backfill"}
_MONITORED_TASK_IDS = (
    "create_airflow_ingestion_run",
    *_WORK_TASK_IDS,
    "finalize_airflow_ingestion_run",
    "resolve_dbt_runtime_context",
    "dbt_compile",
    "dbt_source_freshness",
    "dbt_run_transformations",
    "dbt_test_blocking",
    "dbt_test_warning",
)


def _connect_application_postgres():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
        role=os.getenv("POSTGRES_ROLE", "ecommerce_ingest_writer"),
    )
    connection.autocommit = False
    return connection


def _run_dbt_with_monitoring_summary(
    arguments: list[str],
    *,
    dbt_vars: dict[str, str],
    timeout_seconds: int,
) -> dict[str, int]:
    task_instance = get_current_context()["task_instance"]
    try:
        output = run_dbt_command(
            arguments,
            variables=dbt_vars,
            timeout_seconds=timeout_seconds,
        )
    except DbtCommandError as exc:
        summary = parse_dbt_command_summary(exc.output)
        task_instance.xcom_push(key="monitoring_summary", value=summary)
        raise

    summary = parse_dbt_command_summary(output)
    task_instance.xcom_push(key="monitoring_summary", value=summary)
    return summary


def _get_run_file_audit_counts(
    connection,
    *,
    ingestion_run_id: int,
) -> tuple[int, int, int, int, int]:
    """Aggregate persisted file audit counters for one ingestion run."""
    query = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'success'),
            COUNT(*) FILTER (WHERE status = 'failed'),
            COALESCE(SUM(rows_discovered), 0),
            COALESCE(SUM(rows_loaded), 0),
            COALESCE(SUM(rows_rejected), 0)
        FROM audit.ingestion_files
        WHERE ingestion_run_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (ingestion_run_id,))
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Failed to aggregate ingestion file audit counters: "
            f"ingestion_run_id={ingestion_run_id}"
        )

    return tuple(int(value) for value in row)


def _normalize_airflow_run_type(run_type: object) -> str:
    normalized = getattr(run_type, "value", run_type)

    if not isinstance(normalized, str):
        raise RuntimeError(f"Unsupported Airflow run type value: {run_type!r}")

    if normalized not in _SUPPORTED_AIRFLOW_RUN_TYPES:
        raise RuntimeError(f"Unsupported Airflow run type for ingestion audit: {normalized}")

    return normalized


with DAG(
    dag_id="ecommerce_ingestion",
    schedule=CronDataIntervalTimetable(
        "0 2 * * *", timezone="Asia/Bangkok"
    ),
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Bangkok"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=4,
    dagrun_timeout=timedelta(hours=2),
    is_paused_upon_creation=True,
    tags=["ecommerce", "ingestion", "dbt", "production"],
) as dag:

    @setup
    def create_airflow_ingestion_run() -> int:
        """Create the application audit run for the current Airflow DagRun."""
        context = get_current_context()
        dag_run = context["dag_run"]
        task_instance = context["task_instance"]
        run_type = _normalize_airflow_run_type(dag_run.run_type)

        connection = _connect_application_postgres()

        try:
            with transaction_scope(connection):
                run_state = create_ingestion_run(
                    connection,
                    pipeline_name=task_instance.dag_id,
                    run_type=run_type,
                )
        finally:
            connection.close()

        return run_state.ingestion_run_id

    @task
    def validate_ingestion_runtime() -> tuple[str, ...]:
        """Validate that Airflow can import and execute the ingestion package."""
        source_names = list_source_names()

        if not source_names:
            raise RuntimeError("No ingestion sources are registered")

        return source_names

    @task
    def discover_demo_source_files() -> dict[str, list[dict[str, str]]]:
        """Discover portfolio-safe demo input files using the ingestion service."""
        input_directory = os.environ["DATA_DEMO_DIR"]
        discovered = discover_all_sources(input_directory)

        return {
            source_name: [
                {
                    "file_name": item.file_name,
                    "file_path": str(item.file_path),
                }
                for item in files
            ]
            for source_name, files in discovered.items()
        }

    @task
    def register_discovered_files(
        ingestion_run_id: int,
        discovered: dict[str, list[dict[str, str]]],
    ) -> list[dict[str, str | int]]:
        """Register files and apply the ingestion idempotency policy."""
        metadata_batch = [
            build_file_metadata(
                source_name=source_name,
                file_path=file_info["file_path"],
            )
            for source_name, files in discovered.items()
            for file_info in files
        ]

        registration_results: list[dict[str, str | int]] = []
        connection = _connect_application_postgres()

        try:
            with transaction_scope(connection):
                for metadata in metadata_batch:
                    registration = register_file(
                        connection=connection,
                        ingestion_run_id=ingestion_run_id,
                        metadata=metadata,
                    )
                    decision = decide_file_processing(
                        registration,
                        current_ingestion_run_id=ingestion_run_id,
                    )

                    if decision.action == "block":
                        raise RuntimeError(
                            "File processing blocked by idempotency policy: "
                            f"source={metadata.source_name}, "
                            f"file={metadata.file_name}, "
                            f"reason={decision.reason}"
                        )

                    registration_results.append(
                        {
                            "source_name": metadata.source_name,
                            "file_name": metadata.file_name,
                            "file_path": metadata.file_path,
                            "file_hash_sha256": metadata.file_hash_sha256,
                            "ingestion_file_id": registration.ingestion_file_id,
                            "action": decision.action,
                            "reason": decision.reason,
                        }
                    )
        finally:
            connection.close()

        return registration_results

    @task(
        pool="postgres_ingestion",
        execution_timeout=timedelta(minutes=30),
    )
    def extract_and_validate_registered_files(
        ingestion_run_id: int,
        registered_files: list[dict[str, str | int]],
    ) -> list[dict[str, str | int | list[str]]]:
        """Extract, validate, and load sources with verified load contracts."""
        validation_summaries: list[
            dict[str, str | int | list[str]]
        ] = []
        load_contract_names = set(list_load_contract_names())

        for file_info in registered_files:
            if file_info["action"] != "process":
                continue

            source_name = str(file_info["source_name"])
            file_name = str(file_info["file_name"])
            file_path = str(file_info["file_path"])
            ingestion_file_id = int(file_info["ingestion_file_id"])

            extraction = extract_source_file(
                source_name=source_name,
                file_path=file_path,
            )
            validation = validate_schema(
                source_name=source_name,
                observed_columns=extraction.columns,
            )

            issue_codes = sorted(
                {issue.code for issue in validation.issues}
            )

            if validation.status == "INVALID":
                issues = ",".join(issue_codes) or "none"
                error_message = (
                    "Schema validation failed before load: "
                    f"source={source_name}, "
                    f"file={file_name}, "
                    f"observed_columns="
                    f"{validation.observed_column_count}, "
                    f"expected_columns="
                    f"{validation.expected_column_count}, "
                    f"issues={issues}"
                )

                schema_events = classify_schema_drift(validation)
                connection = _connect_application_postgres()

                try:
                    with transaction_scope(connection):
                        mark_file_processing(
                            connection,
                            ingestion_file_id=ingestion_file_id,
                            rows_discovered=extraction.row_count,
                        )
                        record_schema_events(
                            connection,
                            ingestion_run_id=ingestion_run_id,
                            ingestion_file_id=ingestion_file_id,
                            events=schema_events,
                        )
                        mark_file_failed(
                            connection,
                            ingestion_file_id=ingestion_file_id,
                            rows_discovered=extraction.row_count,
                            rows_loaded=0,
                            rows_rejected=extraction.row_count,
                            error_message=error_message,
                        )
                finally:
                    connection.close()

                raise RuntimeError(error_message)

            rows_loaded = 0
            quality_results = evaluate_source_quality(
                source_name=source_name,
                dataframe=extraction.dataframe,
            )
            blocking_quality_failure = has_blocking_quality_failures(
                quality_results
            )
            quality_failures = [
                result.check_name
                for result in quality_results
                if result.status == "fail"
            ]
            quality_warnings = [
                result.check_name
                for result in quality_results
                if result.status == "warning"
            ]

            if source_name in load_contract_names:
                contract = get_load_contract(source_name)
                lineage = LineageMetadata(
                    source_file=file_name,
                    batch_id=(
                        f"airflow_run_{ingestion_run_id}_"
                        f"file_{ingestion_file_id}"
                    ),
                    file_hash=str(file_info["file_hash_sha256"]),
                    pipeline_run_id=ingestion_run_id,
                    ingestion_file_id=ingestion_file_id,
                )
                connection = _connect_application_postgres()

                try:
                    quality_error_message = (
                        "Data quality validation failed before load: "
                        f"source={source_name}, file={file_name}, "
                        f"checks={','.join(quality_failures)}"
                    )
                    with transaction_scope(connection):
                        mark_file_processing(
                            connection,
                            ingestion_file_id=ingestion_file_id,
                            rows_discovered=extraction.row_count,
                        )
                        record_data_quality_results(
                            connection,
                            ingestion_run_id=ingestion_run_id,
                            ingestion_file_id=ingestion_file_id,
                            source_name=source_name,
                            results=quality_results,
                        )
                        if blocking_quality_failure:
                            mark_file_failed(
                                connection,
                                ingestion_file_id=ingestion_file_id,
                                rows_discovered=extraction.row_count,
                                rows_loaded=0,
                                rows_rejected=extraction.row_count,
                                error_message=quality_error_message,
                            )

                    if blocking_quality_failure:
                        raise RuntimeError(quality_error_message)

                    try:
                        with transaction_scope(connection):
                            load_result = bulk_load_source(
                                connection=connection,
                                source_name=source_name,
                                dataframe=extraction.dataframe,
                                column_mapping=contract.column_mapping,
                                lineage=lineage,
                            )
                            mark_file_success(
                                connection,
                                ingestion_file_id=ingestion_file_id,
                                rows_discovered=extraction.row_count,
                                rows_loaded=load_result.rows_loaded,
                                rows_rejected=(
                                    extraction.row_count
                                    - load_result.rows_loaded
                                ),
                            )
                    except Exception as exc:
                        error_message = (
                            "Bulk load failed: "
                            f"source={source_name}, "
                            f"file={file_name}, "
                            f"error={exc}"
                        )
                        with transaction_scope(connection):
                            mark_file_failed(
                                connection,
                                ingestion_file_id=ingestion_file_id,
                                rows_discovered=extraction.row_count,
                                rows_loaded=0,
                                rows_rejected=extraction.row_count,
                                error_message=error_message,
                            )
                        raise RuntimeError(error_message) from exc
                finally:
                    connection.close()

                rows_loaded = load_result.rows_loaded

            validation_summaries.append(
                {
                    "source_name": source_name,
                    "file_name": file_name,
                    "ingestion_file_id": ingestion_file_id,
                    "row_count": extraction.row_count,
                    "rows_loaded": rows_loaded,
                    "column_count": extraction.column_count,
                    "schema_status": validation.status,
                    "issue_codes": issue_codes,
                    "quality_check_count": len(quality_results),
                    "quality_failures": quality_failures,
                    "quality_warnings": quality_warnings,
                }
            )

        return validation_summaries

    @task
    def resolve_dbt_runtime_context() -> dict[str, str]:
        context = get_current_context()
        dag_run = context["dag_run"]
        variables = resolve_backfill_vars(
            dag_run.run_type,
            context.get("data_interval_start"),
            context.get("data_interval_end"),
        )
        mode = "backfill" if variables else "incremental"
        print(f"dbt execution mode={mode}")
        return variables

    @task(
        pool="dbt_transform",
        execution_timeout=timedelta(minutes=10),
    )
    def dbt_compile(dbt_vars: dict[str, str]) -> None:
        run_dbt_command(
            ["compile"],
            variables=dbt_vars,
            timeout_seconds=480,
        )

    @task(
        pool="dbt_transform",
        execution_timeout=timedelta(minutes=10),
    )
    def dbt_source_freshness(dbt_vars: dict[str, str]) -> dict[str, int]:
        return _run_dbt_with_monitoring_summary(
            ["source", "freshness"],
            dbt_vars=dbt_vars,
            timeout_seconds=480,
        )

    @task(
        pool="dbt_transform",
        retries=2,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=10),
        execution_timeout=timedelta(minutes=45),
    )
    def dbt_run_transformations(dbt_vars: dict[str, str]) -> None:
        run_dbt_command(
            ["run"],
            variables=dbt_vars,
            timeout_seconds=2400,
        )

    @task(
        pool="dbt_transform",
        execution_timeout=timedelta(minutes=30),
    )
    def dbt_test_blocking(dbt_vars: dict[str, str]) -> dict[str, int]:
        return _run_dbt_with_monitoring_summary(
            ["test", "--exclude", "tag:dq_warning"],
            dbt_vars=dbt_vars,
            timeout_seconds=1500,
        )

    @task(
        pool="dbt_transform",
        execution_timeout=timedelta(minutes=15),
    )
    def dbt_test_warning(dbt_vars: dict[str, str]) -> dict[str, int]:
        return _run_dbt_with_monitoring_summary(
            ["test", "--selector", "dq_warning"],
            dbt_vars=dbt_vars,
            timeout_seconds=720,
        )

    @task(
        trigger_rule=TriggerRule.ALL_DONE,
        execution_timeout=timedelta(minutes=5),
    )
    def monitor_pipeline_run() -> None:
        context = get_current_context()
        dag_run = context["dag_run"]
        task_instance = context["task_instance"]

        states_by_run = task_instance.get_task_states(
            dag_id=task_instance.dag_id,
            task_ids=list(_MONITORED_TASK_IDS),
            run_ids=[task_instance.run_id],
        )
        states = states_by_run.get(task_instance.run_id, {})
        task_states = {
            task_id: states.get(task_id, "missing")
            for task_id in _MONITORED_TASK_IDS
        }

        ingestion_run_id = task_instance.xcom_pull(
            task_ids="create_airflow_ingestion_run",
            dag_id=task_instance.dag_id,
            run_id=task_instance.run_id,
            default=None,
        )
        if not isinstance(ingestion_run_id, int):
            ingestion_run_id = None

        freshness_summary = task_instance.xcom_pull(
            task_ids="dbt_source_freshness",
            dag_id=task_instance.dag_id,
            run_id=task_instance.run_id,
            key="monitoring_summary",
            default=None,
        )
        blocking_summary = task_instance.xcom_pull(
            task_ids="dbt_test_blocking",
            dag_id=task_instance.dag_id,
            run_id=task_instance.run_id,
            key="monitoring_summary",
            default=None,
        )
        warning_summary = task_instance.xcom_pull(
            task_ids="dbt_test_warning",
            dag_id=task_instance.dag_id,
            run_id=task_instance.run_id,
            key="monitoring_summary",
            default=None,
        )

        started_at = dag_run.start_date
        if started_at is None:
            raise RuntimeError("DagRun start_date is required for monitoring")
        observed_at = pendulum.now("UTC")
        slow_threshold_seconds = int(
            os.getenv("PIPELINE_SLOW_THRESHOLD_SECONDS", "180")
        )
        notify_warnings = os.getenv(
            "PIPELINE_ALERT_NOTIFY_WARNINGS", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}

        connection = _connect_application_postgres()
        snapshot = None
        alerts = ()
        alert_ids = ()
        try:
            with transaction_scope(connection):
                ingestion = load_ingestion_telemetry(
                    connection, ingestion_run_id
                )
                snapshot = build_pipeline_snapshot(
                    dag_id=task_instance.dag_id,
                    dag_run_id=task_instance.run_id,
                    run_type=_normalize_airflow_run_type(dag_run.run_type),
                    ingestion_run_id=ingestion_run_id,
                    started_at=started_at,
                    observed_at=observed_at,
                    slow_threshold_seconds=slow_threshold_seconds,
                    task_states=task_states,
                    ingestion=ingestion,
                    dbt_freshness_summary=freshness_summary,
                    dbt_blocking_summary=blocking_summary,
                    dbt_warning_summary=warning_summary,
                )
                alerts = build_pipeline_alerts(
                    snapshot, notify_warnings=notify_warnings
                )
                monitoring_run_id = record_pipeline_monitoring_run(
                    connection, snapshot
                )
                alert_ids = record_pipeline_alerts(
                    connection,
                    monitoring_run_id=monitoring_run_id,
                    snapshot=snapshot,
                    alerts=alerts,
                )

            webhook_url = os.getenv("PIPELINE_ALERT_WEBHOOK_URL") or None
            for alert_id, alert in zip(alert_ids, alerts, strict=True):
                delivery = send_webhook_alert(
                    webhook_url=webhook_url,
                    snapshot=snapshot,
                    alert=alert,
                )
                with transaction_scope(connection):
                    update_alert_delivery(
                        connection,
                        pipeline_alert_id=alert_id,
                        status=delivery.status,
                        error=delivery.error,
                    )
        finally:
            connection.close()

        if snapshot is None:
            raise RuntimeError("Monitoring snapshot was not created")
        print(
            "pipeline_monitoring "
            f"status={snapshot.status} duration={snapshot.duration_seconds:.3f}s "
            f"alerts={len(alerts)}"
        )
        if snapshot.status == "failed":
            failed = ", ".join(
                f"{task_id}={state}"
                for task_id, state in task_states.items()
                if state != "success"
            )
            raise RuntimeError(
                "Pipeline monitoring observed upstream failure: " + failed
            )

    @teardown(on_failure_fail_dagrun=True)
    def finalize_airflow_ingestion_run(ingestion_run_id: int) -> None:
        """Finalize the application audit run from the observed Airflow work states."""
        context = get_current_context()
        task_instance = context["task_instance"]

        states_by_run = task_instance.get_task_states(
            dag_id=task_instance.dag_id,
            task_ids=list(_WORK_TASK_IDS),
            run_ids=[task_instance.run_id],
        )
        task_states = states_by_run.get(task_instance.run_id, {})

        state_summary = {
            task_id: task_states.get(task_id, "missing")
            for task_id in _WORK_TASK_IDS
        }
        work_succeeded = all(
            state_summary[task_id] == "success"
            for task_id in _WORK_TASK_IDS
        )

        teardown_error: str | None = None
        connection = _connect_application_postgres()

        try:
            with transaction_scope(connection):
                if work_succeeded:
                    discovered = task_instance.xcom_pull(
                        task_ids="discover_demo_source_files",
                        dag_id=task_instance.dag_id,
                        run_id=task_instance.run_id,
                        default=None,
                    )

                    if not isinstance(discovered, dict):
                        teardown_error = (
                            "Discovery task succeeded but returned no usable "
                            "discovery metadata"
                        )
                        mark_run_failed(
                            connection,
                            ingestion_run_id=ingestion_run_id,
                            files_discovered=0,
                            files_processed=0,
                            files_failed=0,
                            rows_discovered=0,
                            rows_loaded=0,
                            rows_rejected=0,
                            error_message=teardown_error,
                        )
                    else:
                        files_discovered = sum(
                            len(files)
                            for files in discovered.values()
                        )
                        (
                            files_processed,
                            files_failed,
                            rows_discovered,
                            rows_loaded,
                            rows_rejected,
                        ) = _get_run_file_audit_counts(
                            connection,
                            ingestion_run_id=ingestion_run_id,
                        )

                        mark_run_success(
                            connection,
                            ingestion_run_id=ingestion_run_id,
                            files_discovered=files_discovered,
                            files_processed=files_processed,
                            files_failed=files_failed,
                            rows_discovered=rows_discovered,
                            rows_loaded=rows_loaded,
                            rows_rejected=rows_rejected,
                        )
                else:
                    teardown_error = "Airflow work task failure: " + ", ".join(
                        f"{task_id}={state_summary[task_id]}"
                        for task_id in _WORK_TASK_IDS
                    )

                    discovered = task_instance.xcom_pull(
                        task_ids="discover_demo_source_files",
                        dag_id=task_instance.dag_id,
                        run_id=task_instance.run_id,
                        default=None,
                    )
                    files_discovered = (
                        sum(len(files) for files in discovered.values())
                        if isinstance(discovered, dict)
                        else 0
                    )

                    (
                        files_processed,
                        files_failed,
                        rows_discovered,
                        rows_loaded,
                        rows_rejected,
                    ) = _get_run_file_audit_counts(
                        connection,
                        ingestion_run_id=ingestion_run_id,
                    )

                    mark_run_failed(
                        connection,
                        ingestion_run_id=ingestion_run_id,
                        files_discovered=files_discovered,
                        files_processed=files_processed,
                        files_failed=files_failed,
                        rows_discovered=rows_discovered,
                        rows_loaded=rows_loaded,
                        rows_rejected=rows_rejected,
                        error_message=teardown_error,
                    )
        finally:
            connection.close()

        if teardown_error is not None:
            raise RuntimeError(teardown_error)

    ingestion_run_id = create_airflow_ingestion_run()
    ingestion_finalizer = finalize_airflow_ingestion_run(ingestion_run_id)

    with ingestion_finalizer:
        validate_runtime = validate_ingestion_runtime()
        discovered_files = discover_demo_source_files()
        registered_files = register_discovered_files(
            ingestion_run_id=ingestion_run_id,
            discovered=discovered_files,
        )
        validated_files = extract_and_validate_registered_files(
            ingestion_run_id=ingestion_run_id,
            registered_files=registered_files,
        )
        (
            validate_runtime
            >> discovered_files
            >> registered_files
            >> validated_files
        )

    dbt_vars = resolve_dbt_runtime_context()
    compiled = dbt_compile(dbt_vars)
    freshness = dbt_source_freshness(dbt_vars)
    transformed = dbt_run_transformations(dbt_vars)
    blocking_tests = dbt_test_blocking(dbt_vars)
    warning_tests = dbt_test_warning(dbt_vars)
    monitoring = monitor_pipeline_run()

    (
        ingestion_finalizer
        >> dbt_vars
        >> compiled
        >> freshness
        >> transformed
        >> blocking_tests
        >> warning_tests
        >> monitoring
    )


if __name__ == "__main__":
    dag.test()
