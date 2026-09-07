FROM apache/airflow:3.3.0-python3.12

RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" "openpyxl==3.1.5"
