import requests
import os
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from datetime import datetime

response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
data = response.json()
players = data["elements"]

load_dotenv()
conn = psycopg.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"]
)
print(f"Connected successfully!")

with conn.cursor() as cur:
    cur.execute(
        "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded)" \
        "values (%s, %s, %s, %s) returning run_id",
        ("bootstrap_static", datetime.now(), "in_progress", 0)
        )
    run_id = cur.fetchone()[0]
    conn.commit()
print(f"Pipeline run created with run_id: {run_id}")
with conn.cursor() as cur:
    try:
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