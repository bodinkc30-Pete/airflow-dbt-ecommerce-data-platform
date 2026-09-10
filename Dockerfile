FROM apache/airflow:3.3.0-python3.12

COPY requirements-dbt.txt /tmp/requirements-dbt.txt
COPY requirements-airflow-cloud.txt /tmp/requirements-airflow-cloud.txt

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    "openpyxl==3.1.5" \
    -r /tmp/requirements-dbt.txt \
    -r /tmp/requirements-airflow-cloud.txt

USER root
RUN mkdir -p /opt/airflow/auth \
    && chown airflow:root /opt/airflow/auth \
    && chmod 0775 /opt/airflow/auth
USER airflow

ENV PYTHONPATH=/opt/airflow/src

COPY --chown=airflow:root src /opt/airflow/src
COPY --chown=airflow:root airflow/dags /opt/airflow/dags
COPY --chown=airflow:root dbt /opt/airflow/dbt
COPY --chown=airflow:root scripts /opt/airflow/scripts
COPY --chown=airflow:root database /opt/airflow/database
