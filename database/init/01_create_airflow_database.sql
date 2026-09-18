-- Runs once via docker-entrypoint-initdb.d on first container start.
-- PostgreSQL has no CREATE DATABASE IF NOT EXISTS; do not run this file
-- manually against an existing cluster without checking first.
CREATE DATABASE airflow;
