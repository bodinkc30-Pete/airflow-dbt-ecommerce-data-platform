import os

from airflow.sdk import DAG, task

from ecommerce_pipeline.ingestion.file_discovery import discover_all_sources
from ecommerce_pipeline.ingestion.source_registry import list_source_names

with DAG(
    dag_id="ecommerce_ingestion",
    schedule=None,
    catchup=False,
    tags=["ecommerce", "ingestion"],
) as dag:

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

    validate_ingestion_runtime() >> discover_demo_source_files()


if __name__ == "__main__":
    dag.test()
