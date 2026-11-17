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


def python_task(task_id, module):
    """
    Every task in this pipeline is "run one Python module from /opt/airflow".
    I wrote that BashOperator once here instead of 16 times, so a change
    (for example a timeout) is made in one place. The task_ids are exactly
    the same as before, so old run history in the Airflow UI still matches.
    """
    return BashOperator(
        task_id=task_id,
        bash_command=f'cd /opt/airflow && python -m {module}',
    )


with DAG(
    'fpl_data_pipeline',
    default_args=default_args,
    description='End-to-End FPL Data Pipeline (Bronze -> Silver -> Gold)',
    # "schedule" replaces "schedule_interval", which is deprecated since Airflow 2.4.
    schedule='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    # Only one run at a time: two overlapping runs would write the same
    # Bronze/Silver/Gold tables together and the Gate 1 results of one run
    # could be read by the other.
    max_active_runs=1,
    tags=['fpl', 'data-engineering'],
) as dag:

    # ==========================================
    # 1. Ingestion (Bronze)
    # ==========================================
    ingest_bootstrap = python_task('ingest_bootstrap_static', 'src.ingestion.ingest_bootstrap_static')
    ingest_fixtures = python_task('ingest_fixtures', 'src.ingestion.ingest_fixtures')
    ingest_event = python_task('ingest_event', 'src.ingestion.ingest_event')

    # ==========================================
    # 2. Gate 1 Quality Checks
    # ==========================================
    check_players = python_task('check_bronze_players', 'src.quality_checks.check_bronze_players')
    check_teams = python_task('check_bronze_teams', 'src.quality_checks.check_bronze_teams')
    check_fixtures = python_task('check_bronze_fixtures', 'src.quality_checks.check_bronze_fixtures')
    check_event = python_task('check_bronze_event', 'src.quality_checks.check_bronze_event')

    # ==========================================
    # 3. Silver Transformations
    # ==========================================
    transform_players = python_task('transform_players', 'src.transformation.transform_players')
    transform_teams = python_task('transform_teams', 'src.transformation.transform_teams')
    transform_fixtures = python_task('transform_fixtures', 'src.transformation.transform_fixtures')
    transform_element_types = python_task('transform_element_types', 'src.transformation.transform_element_types')
    transform_gw_stats = python_task('transform_player_gameweek_stats', 'src.transformation.transform_player_gameweek_stats')

    # ==========================================
    # 4. Gold Population
    # ==========================================
    populate_teams = python_task('populate_gold_teams', 'src.transformation.populate_gold_teams')
    populate_players = python_task('populate_gold_players', 'src.transformation.populate_gold_players')
    populate_fixtures = python_task('populate_gold_fixture_results', 'src.transformation.populate_gold_fixture_results')
    populate_gw_perf = python_task('populate_gold_player_gameweek_performance', 'src.transformation.populate_gold_player_gameweek_performance')
    # This one was missing from the DAG: question 3 (price over time) had a
    # Gold table that the pipeline never filled.
    populate_price_history = python_task('populate_gold_player_price_history', 'src.transformation.populate_gold_player_price_history')

    # ==========================================
    # 5. Gate 2 Reconciliation
    # ==========================================
    check_reconciliation = python_task('check_gold_reconciliation', 'src.quality_checks.check_gold_reconciliation')

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

    # Gold player_gameweek_performance and player_price_history both have a
    # Foreign Key to Gold players, so they MUST wait for populate_players.
    # Before, populate_gw_perf only waited for transform_gw_stats, so it
    # could start before the Gold players rows existed and fail on the FK.
    transform_gw_stats >> populate_gw_perf
    populate_players >> [populate_gw_perf, populate_price_history]

    # Gate 2 runs last
    [populate_teams, populate_players, populate_fixtures,
     populate_gw_perf, populate_price_history] >> check_reconciliation
