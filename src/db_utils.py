"""
db_utils.py - shared database connection and shared ingestion logic.

I keep this separate from any single ingestion script, because every part
of the pipeline (ingestion, quality checks, transformation) needs to connect
to Postgres and reuse the same JSONB ingestion pattern. I write it once here,
and import it everywhere else, instead of repeating the same code.
"""

import os
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from datetime import datetime, timezone


def get_connection():
    load_dotenv()
    conn = psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    )
    print(f"Connected successfully!")
    return conn


def ingest_jsonb_entity(conn, entity_name, singular_name, entity_data,
                         source_name, get_snapshot_type):
    """
    I use this one function for players, teams, and fixtures - they all
    have the same shape (raw JSON stored as-is). I do NOT use it for
    element_types, because that table is flattened into real columns
    instead of JSONB - different shape, so it needs its own function.

    Each call gets its own pipeline_runs row and its own try/except with
    rollback. This is task-level isolation: if teams fails, it should
    never roll back or block players, which is more important data.

    get_snapshot_type is a function I pass in, not a fixed value. For
    players/teams, the snapshot_type is the same for every row, so I pass
    a small function that just returns that one fixed value. For fixtures,
    every fixture is different (some finished, some not), so I pass a
    function that actually looks at each fixture and decides.
    """
    with conn.cursor() as cur:
        cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded) " \
            "values (%s, %s, %s, %s) returning run_id",
            (source_name, datetime.now(), "in_progress", 0)
        )
        run_id = cur.fetchone()[0]
        conn.commit()
    print(f"Pipeline run created with run_id: {run_id}")

    with conn.cursor() as cur:
        try:
            # Jsonb() wraps each raw dict so psycopg saves it correctly into
            # the raw_json jsonb column. The id is taken out separately for
            # the dedicated {singular_name}_id column.
            for item in entity_data:
                cur.execute(
                    f"insert into bronze_{entity_name} ({singular_name}_id, raw_json, load_date, "
                    f"snapshot_type, run_id) values (%s, %s, %s, %s, %s)",
                    (item["id"], Jsonb(item), datetime.now(), get_snapshot_type(item), run_id)
                )
            cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(entity_data), run_id)
            )
            conn.commit()
            print(f"Inserted {len(entity_data)} {entity_name} into the database.")
        except Exception as e:
            # rollback undoes all partial inserts from this loop - no half
            # success state. Then I update pipeline_runs with the real error,
            # so I can see failures the same day, not find out later.
            conn.rollback()
            print(f"Error occurred: {e}")
            cur.execute(
                "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
                ("failed", str(e), run_id)
            )
            conn.commit()


def determine_snapshot_type(events):
    """
    I use the events list from bootstrap-static to figure out where we are
    right now in the season: before a deadline, during a live gameweek, or
    after a gameweek finished.

    I return two things: the label, and the gameweek number - but the
    gameweek number is only real when the label is "post_gameweek" (I need
    this number later, to know which gameweek to pull event data for). For
    "deadline" and "live", I return None as the second value, so the shape
    stays the same every time. This matters: if one branch returned just
    one value, unpacking it into two variables would silently break in a
    confusing way (I actually tested this and saw it happen with strings).
    """
    now = datetime.now(timezone.utc)
    future_events = [
        e for e in events
        if datetime.fromisoformat(e['deadline_time'].replace("Z", "+00:00")) > now
    ]
    if future_events:
        next_event = min(
            future_events,
            key=lambda e: datetime.fromisoformat(e['deadline_time'].replace("Z", "+00:00"))
        )
        next_deadline = datetime.fromisoformat(
            next_event['deadline_time'].replace("Z", "+00:00")
        )
        if next_deadline.date() == now.date():
            return "deadline", None
    past_events = [
        e for e in events
        if datetime.fromisoformat(e['deadline_time'].replace("Z", "+00:00")) <= now
    ]
    if past_events:
        latest_event = max(
            past_events,
            key=lambda e: datetime.fromisoformat(e['deadline_time'].replace("Z", "+00:00"))
        )
        if latest_event['finished']:
            return "post_gameweek", latest_event['id']
        return "live", None


def determine_fixture_snapshot_type(fixture):
    """
    Unlike determine_snapshot_type, this one only needs ONE fixture at a
    time - each fixture already carries its own started/finished status,
    so I don't need to compare it against other fixtures to know its state.
    """
    if not fixture["started"]:
        return "pre_match"
    elif fixture["started"] and not fixture["finished"]:
        return "live"
    else:
        return "post_match"