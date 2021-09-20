#!/bin/bash

cp postgres_migration.py ~/airflow/dags
airflow connections add 'postgres_db_1' --conn-uri 'docker://root:root@localhost:5432/source_db'
airflow connections add 'postgres_db_2' --conn-uri 'docker://root:root@localhost:5433/target_db'