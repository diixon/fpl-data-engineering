import requests
from datetime import datetime
from src.db_utils import get_connection, ingest_jsonb_entity, determine_snapshot_type


def ingest_element_types(conn, element_types):
    """
    I keep this separate from ingest_jsonb_entity, because bronze_element_types
    uses real named columns instead of raw_json - this data is simple and
    flat (no nested structures), so I store it directly in typed columns.

    I only use this function here, for this one source - no other script
    will ever need it, so it doesn't need to live in db_utils.py.
    """
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
            for item in element_types:
                cur.execute(
                    "insert into bronze_element_types (element_type_id, plural_name, " \
                    "singular_name, singular_name_short, squad_select, squad_min_play, " \
                    "squad_max_play, element_count, load_date, run_id)" \
                    " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (item["id"], item["plural_name"], item["singular_name"],
                     item["singular_name_short"], item["squad_select"], item["squad_min_play"],
                     item["squad_max_play"], item["element_count"], datetime.now(), run_id)
                )
            cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(element_types), run_id)
            )
            conn.commit()
            print(f"Inserted {len(element_types)} element types into the database.")
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
    players = data["elements"]
    teams = data["teams"]
    elements_types = data["element_types"]
    events = data["events"]

    conn = get_connection()

    # I calculate the snapshot_type ONCE here, not inside the loop - players
    # and teams don't need a different value per item, so I don't want to
    # recalculate the same thing 600+ times for nothing.
    current_snapshot, gw = determine_snapshot_type(events)

    ingest_jsonb_entity(conn, "players", "player", players,
                         "bootstrap_static_players", lambda item: current_snapshot)
    ingest_jsonb_entity(conn, "teams", "team", teams,
                         "bootstrap_static_teams", lambda item: current_snapshot)
    ingest_element_types(conn, elements_types)
    conn.close()