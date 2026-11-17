"""
Shared test setup.

Each test gets its OWN temporary schema, built from my real SQL files (the
same ones init-db.sh runs), and the schema is dropped at the end. So the
tests check the real tables, constraints and foreign keys, and they never
touch the real data in the public schema.

The tests need a running Postgres (for example: docker compose up -d postgres)
and DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD in .env or the
environment. If the database is not reachable, the DB tests are skipped.
"""
import pathlib
import uuid
from datetime import datetime

import pytest
from psycopg.types.json import Jsonb

from src.db_utils import get_connection

ROOT = pathlib.Path(__file__).resolve().parents[1]
SQL_ORDER = [
    "bronze/create_pipeline_runs.sql",
    "bronze/create_bronze_tables.sql",
    "silver/create_silver_tables.sql",
    "silver/add_silver_constraints.sql",
    "gold/create_gold_tables.sql",
    "quality_checks/create_quality_check_results.sql",
]


@pytest.fixture
def db():
    try:
        conn = get_connection()
    except Exception as e:  # no database running -> skip, do not fail
        pytest.skip(f"Postgres is not reachable: {e}")

    schema = f"test_{uuid.uuid4().hex[:8]}"
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {schema}")
        cur.execute(f"SET search_path TO {schema}")
        for sql_file in SQL_ORDER:
            cur.execute((ROOT / "sql" / sql_file).read_text())
    conn.commit()

    yield conn

    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA {schema} CASCADE")
    conn.commit()
    conn.close()


@pytest.fixture
def run_id(db):
    """One pipeline_runs row that the test data can point to."""
    with db.cursor() as cur:
        cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded) "
            "values ('test', now(), 'success', 0) returning run_id"
        )
        rid = cur.fetchone()[0]
    db.commit()
    return rid


STATS = {"minutes": 90, "goals_scored": 1, "assists": 0, "clean_sheets": 0,
         "total_points": 6, "bonus": 1, "bps": 30,
         "expected_goals": "0.45", "expected_assists": "0.10"}


class Seed:
    """Small helpers that put test rows into Bronze."""

    def __init__(self, conn, run_id):
        self.conn, self.run_id = conn, run_id

    def _insert(self, sql, params):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
        self.conn.commit()

    def team(self, team_id=1):
        raw = {"id": team_id, "name": f"Team{team_id}", "short_name": f"T{team_id}",
               "points": 0, "played": 0, "position": team_id, "win": 0, "draw": 0, "loss": 0}
        self._insert("insert into bronze_teams (team_id, raw_json, load_date, snapshot_type, run_id) "
                     "values (%s, %s, %s, 'live', %s)", (team_id, Jsonb(raw), datetime.now(), self.run_id))

    def element_type(self, element_type_id=1):
        self._insert(
            "insert into bronze_element_types (element_type_id, plural_name, singular_name, "
            "singular_name_short, squad_select, squad_min_play, squad_max_play, element_count, "
            "load_date, run_id) values (%s,'Mids','Mid','MID',5,2,5,100,%s,%s)",
            (element_type_id, datetime.now(), self.run_id))

    def player(self, player_id, status="a", load_date=None, drop_keys=(), cost=50, cost_change=0):
        raw = {"id": player_id, "web_name": f"p{player_id}", "element_type": 1, "team": 1,
               "now_cost": cost, "status": status, "transfers_in_event": 5,
               "cost_change_event": cost_change}
        for k in drop_keys:
            raw.pop(k)
        self._insert("insert into bronze_players (player_id, raw_json, load_date, snapshot_type, run_id) "
                     "values (%s, %s, %s, 'live', %s)",
                     (player_id, Jsonb(raw), load_date or datetime.now(), self.run_id))

    def event(self, player_id, gameweek=1):
        self._insert("insert into bronze_event (player_id, gameweek, raw_json, load_date, snapshot_type, run_id) "
                     "values (%s, %s, %s, %s, 'post_gameweek', %s)",
                     (player_id, gameweek, Jsonb({"id": player_id, "stats": STATS}), datetime.now(), self.run_id))


@pytest.fixture
def seed(db, run_id):
    return Seed(db, run_id)


def scalar(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]
