import requests
from datetime import datetime
from psycopg.types.json import Jsonb
from src.db_utils import get_connection, determine_snapshot_type


def ingest_event(conn, gameweek, event_data):
    """
    I only ever call this once a gameweek is fully finished - bronze_event
    has a UNIQUE(player_id, gameweek) constraint, so I can't pull the same
    gameweek's live data more than once. If I pulled it while still live,
    I'd get partial stats, and I'd never be able to insert the complete
    version later without breaking that constraint.
    """
    with conn.cursor() as cur:
        cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded) " \
            "values (%s, %s, %s, %s) returning run_id",
            (f"event_gameweek{gameweek}", datetime.now(), "in_progress", 0)
        )
        run_id = cur.fetchone()[0]
        conn.commit()
    print(f"Pipeline run created with run_id: {run_id}")

    with conn.cursor() as cur:
        try:
            for item in event_data:
                cur.execute(
                    "insert into bronze_event (player_id, gameweek, raw_json, load_date, " \
                    "snapshot_type, run_id) values (%s, %s, %s, %s, %s, %s)",
                    (item["id"], gameweek, Jsonb(item), datetime.now(), "post_gameweek", run_id)
                )
            cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(event_data), run_id)
            )
            conn.commit()
            print(f"Inserted {len(event_data)} events into the database.")
        except Exception as e:
            conn.rollback()
            print(f"Error occurred: {e}")
            cur.execute(
                "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
                ("failed", str(e), run_id)
            )
            conn.commit()


if __name__ == "__main__":
    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    data = response.json()
    events = data["events"]

    label, gw = determine_snapshot_type(events)
    print(f"Current state: {label}, gameweek: {gw}")

    # I only pull and insert event data if the gameweek is actually finished.
    # If it's still live or before deadline, I do nothing - this script is
    # meant to run daily forever, and most days it will just print this
    # message and exit, until the day a gameweek actually finishes.
    if label == "post_gameweek":
        event_response = requests.get(
            f"https://fantasy.premierleague.com/api/event/{gw}/live/"
        )
        event_data = event_response.json()["elements"]

        conn = get_connection()
        ingest_event(conn, gw, event_data)
        conn.close()
    else:
        print("Gameweek not finished yet — nothing to ingest.")