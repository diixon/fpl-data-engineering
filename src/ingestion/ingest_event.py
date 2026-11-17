import sys
from datetime import datetime
from psycopg.types.json import Jsonb
from src.db_utils import (
    get_connection, fetch_json, determine_snapshot_type,
    start_pipeline_run, mark_run_success, mark_run_failed,
)

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
EVENT_URL = "https://fantasy.premierleague.com/api/event/{gw}/live/"


def gameweek_already_ingested(conn, gameweek):
    """
    True if bronze_event already holds this gameweek.

    Why this exists: the DAG runs every day, and after a gameweek finishes
    the state stays "post_gameweek" for several days. Without this check,
    every run after the first one tried to insert the same (player_id,
    gameweek) again, hit the UNIQUE constraint, and was recorded as a
    failed run in pipeline_runs - a false alarm every single day.
    """
    with conn.cursor() as cur:
        cur.execute("select 1 from bronze_event where gameweek = %s limit 1", (gameweek,))
        return cur.fetchone() is not None


def ingest_event(conn, gameweek, event_data, raise_on_error=False):
    """
    I only ever call this once a gameweek is fully finished - bronze_event
    has a UNIQUE(player_id, gameweek) constraint, so I can't pull the same
    gameweek's live data more than once. If I pulled it while still live,
    I'd get partial stats, and I'd never be able to insert the complete
    version later without breaking that constraint.

    Returns True on success, False on failure (same contract as
    ingest_jsonb_entity).
    """
    run_id = start_pipeline_run(conn, f"event_gameweek{gameweek}")

    try:
        load_time = datetime.now()
        rows = [
            (item["id"], gameweek, Jsonb(item), load_time, "post_gameweek", run_id)
            for item in event_data
        ]
        with conn.cursor() as cur:
            cur.executemany(
                "insert into bronze_event (player_id, gameweek, raw_json, load_date, "
                "snapshot_type, run_id) values (%s, %s, %s, %s, %s, %s)",
                rows
            )
            mark_run_success(cur, run_id, len(rows))
        conn.commit()
        print(f"Inserted {len(rows)} events into the database.")
        return True
    except Exception as e:
        mark_run_failed(conn, run_id, e)
        if raise_on_error:
            raise
        return False


def main():
    """Returns the exit code (0 = fine or nothing to do, 1 = the load failed)."""
    events = fetch_json(BOOTSTRAP_URL)["events"]

    label, gw = determine_snapshot_type(events)
    print(f"Current state: {label}, gameweek: {gw}")

    # I only pull and insert event data if the gameweek is actually finished.
    # If it's still live or before deadline, I do nothing - this script is
    # meant to run daily forever, and most days it will just print this
    # message and exit, until the day a gameweek actually finishes.
    if label != "post_gameweek":
        print("Gameweek not finished yet — nothing to ingest.")
        return 0

    with get_connection() as conn:
        if gameweek_already_ingested(conn, gw):
            print(f"Gameweek {gw} is already in bronze_event — nothing to ingest.")
            return 0

        event_data = fetch_json(EVENT_URL.format(gw=gw))["elements"]
        ok = ingest_event(conn, gw, event_data)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
