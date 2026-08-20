from airflow.sdk import DAG, task

from ecommerce_pipeline.ingestion.source_registry import list_source_names

with DAG(
    dag_id="ecommerce_ingestion",
    schedule=None,
    catchup=False,
    tags=["ecommerce", "ingestion"],
) as dag:

    @task
    def validate_ingestion_runtime() -> list[str]:
        """Validate that Airflow can import and execute the ingestion package."""
        source_names = list_source_names()

        if not source_names:
            raise RuntimeError("No ingestion sources are registered")

        return source_names

    validate_ingestion_runtime()


if __name__ == "__main__":
    dag.test()
