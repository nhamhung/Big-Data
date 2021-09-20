import datetime

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator


def migrate_data():
    src = PostgresHook(postgres_conn_id='postgres_db_1')
    dest = PostgresHook(postgres_conn_id='postgres_db_2')
    src_conn = src.get_conn()
    src_cursor = src_conn.cursor()
    dest_conn = dest.get_conn()
    dest_cursor = dest_conn.cursor()
    src_cursor.execute('SELECT * FROM data;')
    dest.insert_rows(table='data', rows=src_cursor)
    dest_cursor.execute('SELECT * FROM data;')


with DAG(
    dag_id="postgres_operator_dag",
    start_date=datetime.datetime(2021, 9, 19),
    schedule_interval="@once",
    catchup=False,
) as dag:
    create_table = PostgresOperator(
        task_id="create_target_table",
        postgres_conn_id="postgres_db_2",
        sql="""
            DROP TABLE IF EXISTS data;
            CREATE TABLE IF NOT EXISTS data (
            id INT NOT NULL,
            creation_date TIMESTAMP NOT NULL,
            sale_value INT NOT NULL,
            PRIMARY KEY (id)
            );
          """,
    )

    migrate_data_hook = PythonOperator(
        task_id="migrate_data", python_callable=migrate_data)

    create_table >> migrate_data_hook
