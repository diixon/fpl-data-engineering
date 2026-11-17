#!/bin/bash
set -e

# I use this script to initialize the database on the very first startup.
# It runs inside the Postgres container before the database accepts external connections.

# Folder that holds my SQL files (the compose file mounts ./sql here).
# I can override it with the SQL_DIR variable to test this script outside Docker.
SQL_DIR="${SQL_DIR:-/docker-entrypoint-initdb.d/sql}"

# 1. I create the Airflow metadata database first, because Airflow needs it to start.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE airflow;
    GRANT ALL PRIVILEGES ON DATABASE airflow TO $POSTGRES_USER;
EOSQL

# 2. I execute all my project SQL files in the exact dependency order.
# Why: Bronze must exist before Silver, and Silver before Gold.
# If I run them out of order, the Foreign Key constraints will fail.
# The list is written once, so adding a new file is one new line, and the
# log shows which file is running (easy to see where it stopped on an error).
SQL_FILES=(
    bronze/create_pipeline_runs.sql
    bronze/create_bronze_tables.sql
    silver/create_silver_tables.sql
    silver/add_silver_constraints.sql
    gold/create_gold_tables.sql
    quality_checks/create_quality_check_results.sql
)

for sql_file in "${SQL_FILES[@]}"; do
    echo "Running $sql_file ..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$SQL_DIR/$sql_file"
done
