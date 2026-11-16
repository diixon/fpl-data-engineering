from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'fpl_data_pipeline',
    default_args=default_args,
    description='End-to-End FPL Data Pipeline (Bronze -> Silver -> Gold)',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['fpl', 'data-engineering'],
) as dag:

    # ==========================================
    # 1. Ingestion (Bronze)
    # ==========================================
    ingest_bootstrap = BashOperator(
        task_id='ingest_bootstrap_static', 
        bash_command='cd /opt/airflow && python -m src.ingestion.ingest_bootstrap_static'
    )
    ingest_fixtures = BashOperator(
        task_id='ingest_fixtures', 
        bash_command='cd /opt/airflow && python -m src.ingestion.ingest_fixtures'
    )
    ingest_event = BashOperator(
        task_id='ingest_event', 
        bash_command='cd /opt/airflow && python -m src.ingestion.ingest_event'
    )

    # ==========================================
    # 2. Gate 1 Quality Checks
    # ==========================================
    check_players = BashOperator(
        task_id='check_bronze_players', 
        bash_command='cd /opt/airflow && python -m src.quality_checks.check_bronze_players'
    )
    check_teams = BashOperator(
        task_id='check_bronze_teams', 
        bash_command='cd /opt/airflow && python -m src.quality_checks.check_bronze_teams'
    )
    check_fixtures = BashOperator(
        task_id='check_bronze_fixtures', 
        bash_command='cd /opt/airflow && python -m src.quality_checks.check_bronze_fixtures'
    )
    check_event = BashOperator(
        task_id='check_bronze_event', 
        bash_command='cd /opt/airflow && python -m src.quality_checks.check_bronze_event'
    )

    # ==========================================
    # 3. Silver Transformations
    # ==========================================
    transform_players = BashOperator(
        task_id='transform_players', 
        bash_command='cd /opt/airflow && python -m src.transformation.transform_players'
    )
    transform_teams = BashOperator(
        task_id='transform_teams', 
        bash_command='cd /opt/airflow && python -m src.transformation.transform_teams'
    )
    transform_fixtures = BashOperator(
        task_id='transform_fixtures', 
        bash_command='cd /opt/airflow && python -m src.transformation.transform_fixtures'
    )
    transform_element_types = BashOperator(
        task_id='transform_element_types', 
        bash_command='cd /opt/airflow && python -m src.transformation.transform_element_types'
    )
    transform_gw_stats = BashOperator(
        task_id='transform_player_gameweek_stats', 
        bash_command='cd /opt/airflow && python -m src.transformation.transform_player_gameweek_stats'
    )

    # ==========================================
    # 4. Gold Population
    # ==========================================
    populate_teams = BashOperator(
        task_id='populate_gold_teams', 
        bash_command='cd /opt/airflow && python -m src.transformation.populate_gold_teams'
    )
    populate_players = BashOperator(
        task_id='populate_gold_players', 
        bash_command='cd /opt/airflow && python -m src.transformation.populate_gold_players'
    )
    populate_fixtures = BashOperator(
        task_id='populate_gold_fixture_results', 
        bash_command='cd /opt/airflow && python -m src.transformation.populate_gold_fixture_results'
    )
    populate_gw_perf = BashOperator(
        task_id='populate_gold_player_gameweek_performance', 
        bash_command='cd /opt/airflow && python -m src.transformation.populate_gold_player_gameweek_performance'
    )
    
    # ==========================================
    # 5. Gate 2 Reconciliation
    # ==========================================
    check_reconciliation = BashOperator(
        task_id='check_gold_reconciliation', 
        bash_command='cd /opt/airflow && python -m src.quality_checks.check_gold_reconciliation'
    )

    # ==========================================
    # DAG Dependencies (The Order of Execution)
    # ==========================================
    
    # Ingestion runs first
    ingest_bootstrap >> [check_players, check_teams, transform_element_types]
    ingest_fixtures >> check_fixtures
    ingest_event >> check_event

    # I enforce that transform_teams MUST finish before players and fixtures.
    # Why: Silver players and fixtures have Foreign Keys pointing to silver_teams.
    # If they run in parallel, the Foreign Key constraint will fail.
    check_teams >> transform_teams
    check_players >> transform_players
    check_fixtures >> transform_fixtures
    
    transform_teams >> [transform_players, transform_fixtures]
    transform_element_types >> transform_players
    
    # Gameweek stats need players to exist first
    [transform_players, check_event] >> transform_gw_stats

    # Gold Population runs after Silver transformations
    transform_teams >> populate_teams
    transform_players >> populate_players
    transform_fixtures >> populate_fixtures
    transform_gw_stats >> populate_gw_perf
    
    # Gate 2 runs last
    [populate_teams, populate_players, populate_fixtures, populate_gw_perf] >> check_reconciliation