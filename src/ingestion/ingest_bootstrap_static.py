import requests
import os
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from datetime import datetime

response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
data = response.json()
players = data["elements"]
teams = data["teams"]
elements_types = data["element_types"]

load_dotenv()
conn = psycopg.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"]
)
print(f"Connected successfully!")

# Three independent pipeline_runs/try-except blocks (players, teams,
# element_types) instead of one combined block - task-level isolation.
# If teams or element_types fail, it doesn't affect the players ingestion,
# which is the more critical, time-sensitive data. A failed teams load is
# low-impact (team names rarely change) and shouldn't block or roll back
# already-successful player data.

# pipeline_runs insert happens in its own committed block, separate from the
# main try/except - we need run_id available and guaranteed saved before
# anything risky starts, so failures can always be traced back to this run.
with conn.cursor() as cur:
    cur.execute(
        "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded)" \
        "values (%s, %s, %s, %s) returning run_id",
        ("bootstrap_static_players", datetime.now(), "in_progress", 0)
        )
    run_id = cur.fetchone()[0]
    conn.commit()
print(f"Pipeline run created with run_id: {run_id}")

# try/except wraps the whole insert loop: if anything fails partway through,
# rollback() undoes all partial inserts (no half-success/half-failure state),
# and the except block records the real error into pipeline_runs for same-day
# debugging instead of a silent crash.
with conn.cursor() as cur:
    try:
            # Jsonb() wraps the player dict so psycopg correctly serializes it
            # into the raw_json jsonb column. player_id is extracted separately
            # via player["id"] for the dedicated player_id column.
            #
            # snapshot_type is hardcoded to "post_gameweek" for now - this only
            # reflects today's actual pipeline state (GW2 finished, GW3 deadline
            # not yet reached).
            # TODO: make this dynamic based on real deadline/gameweek timing
            # once pipeline scheduling logic is built.
        for player in players:
            cur.execute(
                "insert into bronze_players (player_id, raw_json, load_date," \
                "snapshot_type, run_id) values (%s, %s, %s, %s, %s)",
                (player["id"], Jsonb(player), datetime.now(), "post_gameweek", run_id)
            )
        cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(players), run_id)
            )
        conn.commit()
        print(f"Inserted {len(players)} players into the database.")
    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
        cur.execute(
            "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
            ("failed", str(e), run_id)
        )
        conn.commit()

with conn.cursor() as cur:
    cur.execute(
        "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded)" \
        " values (%s, %s, %s, %s) returning run_id",
        ("bootstrap_static_teams", datetime.now(), "in_progress", 0)
    )
    run_id = cur.fetchone()[0]
    conn.commit()
    print(f"Pipeline run created with run_id: {run_id}")

with conn.cursor() as cur:
    try:
        for team in teams:
            cur.execute(
                "insert into bronze_teams (team_id, raw_json, load_date, snapshot_type, run_id)" \
                " values (%s, %s, %s, %s, %s)",
                (team["id"], Jsonb(team), datetime.now(), "post_gameweek", run_id)
            )
        cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(teams), run_id)
            )
        conn.commit()
        print(f"Inserted {len(teams)} teams into the database.")
    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
        cur.execute(
            "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
            ("failed", str(e), run_id)
        )
        conn.commit()

with conn.cursor() as cur:
    cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded) " \
            "values (%s, %s, %s, %s) returning run_id",
            ("bootstrap_static_element_types", datetime.now(), "in_progress", 0)
        )
    run_id = cur.fetchone()[0]
    conn.commit()
    print(f"Pipeline run created with run_id: {run_id}")

with conn.cursor() as cur:
    try:
        # bronze_element_types uses individual named fields instead of Jsonb() -
        # unlike players/teams, this source data is simple and flat (no nested
        # structures), so it's easy and safe to flatten directly into typed columns.
        for element_type in elements_types:
        #|element_type_id|plural_name|singular_name|singular_name_short|squad_select|squad_min_play|squad_max_play|element_count|load_date|run_id|
            cur.execute(
                "insert into bronze_element_types (element_type_id, plural_name, singular_name," \
                " singular_name_short, squad_select, squad_min_play, squad_max_play," \
                " element_count, load_date, run_id) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (element_type["id"], element_type["plural_name"], element_type["singular_name"],
                 element_type["singular_name_short"], element_type["squad_select"],
                 element_type["squad_min_play"], element_type["squad_max_play"],
                 element_type["element_count"], datetime.now(), run_id)
            )
        cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(elements_types), run_id)
            )
        conn.commit()
        print(f"Inserted {len(elements_types)} element types into the database.")
    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
        cur.execute(
            "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
            ("failed", str(e), run_id)
        )
        conn.commit()