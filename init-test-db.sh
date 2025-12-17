#!/bin/bash
set -e

# This script runs when postgres container first starts
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE task_manager_test;
    GRANT ALL PRIVILEGES ON DATABASE task_manager_test TO task_user;
EOSQL