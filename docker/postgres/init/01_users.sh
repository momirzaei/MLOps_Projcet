#!/bin/bash
set -e

required_vars=(
  POSTGRES_USER
  POSTGRES_DB
  DWH_OWNER_USER
  DWH_OWNER_PASSWORD
  DWH_READONLY_USER
  DWH_READONLY_PASSWORD
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 1
  fi
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
    \getenv dwh_owner_user DWH_OWNER_USER
    \getenv dwh_owner_password DWH_OWNER_PASSWORD
    \getenv dwh_readonly_user DWH_READONLY_USER
    \getenv dwh_readonly_password DWH_READONLY_PASSWORD

    CREATE DATABASE mlflow;

    CREATE USER :"dwh_owner_user" WITH PASSWORD :'dwh_owner_password';
    CREATE USER :"dwh_readonly_user" WITH PASSWORD :'dwh_readonly_password';

    -- SQL-safety: hard statement timeout for the read-only role
    ALTER ROLE :"dwh_readonly_user" SET statement_timeout = '10s';
EOSQL
