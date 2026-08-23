import os

from airflow.sdk import DAG, get_current_context, setup, task, teardown

from ecommerce_pipeline.ingestion.file_discovery import discover_all_sources
from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.run_lifecycle import (
    create_ingestion_run,
    mark_run_failed,
    mark_run_success,
)
from ecommerce_pipeline.ingestion.source_registry import list_source_names
from ecommerce_pipeline.ingestion.transaction import transaction_scope

_WORK_TASK_IDS = (
    "validate_ingestion_runtime",
    "discover_demo_source_files",
)
_SUPPORTED_AIRFLOW_RUN_TYPES = {"manual", "scheduled", "backfill"}


def _connect_application_postgres():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.autocommit = False
    return connection


def _normalize_airflow_run_type(run_type: object) -> str:
    normalized = getattr(run_type, "value", run_type)

    if not isinstance(normalized, str):
        raise RuntimeError(f"Unsupported Airflow run type value: {run_type!r}")

    if normalized not in _SUPPORTED_AIRFLOW_RUN_TYPES:
        raise RuntimeError(f"Unsupported Airflow run type for ingestion audit: {normalized}")

    return normalized


with DAG(
    dag_id="ecommerce_ingestion",
    schedule=None,
    catchup=False,
    tags=["ecommerce", "ingestion"],
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
    def discover_demo_source_files() -> dict[str, list[str]]:
        """Discover portfolio-safe demo input files using the ingestion service."""
        input_directory = os.environ["DATA_DEMO_DIR"]
        discovered = discover_all_sources(input_directory)

        return {
            source_name: [item.file_name for item in files]
            for source_name, files in discovered.items()
        }

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

                        mark_run_success(
                            connection,
                            ingestion_run_id=ingestion_run_id,
                            files_discovered=files_discovered,
                            files_processed=0,
                            files_failed=0,
                            rows_discovered=0,
                            rows_loaded=0,
                            rows_rejected=0,
                        )
                else:
                    teardown_error = "Airflow work task failure: " + ", ".join(
                        f"{task_id}={state_summary[task_id]}"
                        for task_id in _WORK_TASK_IDS
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
        finally:
            connection.close()

        if teardown_error is not None:
            raise RuntimeError(teardown_error)

    ingestion_run_id = create_airflow_ingestion_run()

    with finalize_airflow_ingestion_run(ingestion_run_id):
        validate_runtime = validate_ingestion_runtime()
        discovered_files = discover_demo_source_files()

        validate_runtime >> discovered_files


if __name__ == "__main__":
    dag.test()
