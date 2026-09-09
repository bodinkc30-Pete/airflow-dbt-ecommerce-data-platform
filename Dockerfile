FROM apache/airflow:3.3.0-python3.12

COPY requirements-dbt.txt /tmp/requirements-dbt.txt

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    "openpyxl==3.1.5" \
    -r /tmp/requirements-dbt.txt
