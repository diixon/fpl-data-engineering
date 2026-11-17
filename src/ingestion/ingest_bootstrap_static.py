import sys
from datetime import datetime
from src.db_utils import (
    get_connection, fetch_json, ingest_jsonb_entity, determine_snapshot_type,
    start_pipeline_run, mark_run_success, mark_run_failed,
)

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def ingest_element_types(conn, element_types, raise_on_error=False):
    """
    I keep this separate from ingest_jsonb_entity, because bronze_element_types
    uses real named columns instead of raw_json - this data is simple and
    flat (no nested structures), so I store it directly in typed columns.

    I only use this function here, for this one source - no other script
    will ever need it, so it doesn't need to live in db_utils.py. The
    pipeline_runs tracking itself (start / success / failed) is NOT repeated
    here anymore: it uses the same three helpers from db_utils as every
    other ingestion, so the logic exists once.

    Returns True on success, False on failure (same contract as
    ingest_jsonb_entity).
    """
    run_id = start_pipeline_run(conn, "bootstrap_static_element_types")

    try:
        load_time = datetime.now()
        rows = [
            (item["id"], item["plural_name"], item["singular_name"],
             item["singular_name_short"], item["squad_select"], item["squad_min_play"],
             item["squad_max_play"], item["element_count"], load_time, run_id)
            for item in element_types
        ]
        with conn.cursor() as cur:
            cur.executemany(
                "insert into bronze_element_types (element_type_id, plural_name, "
                "singular_name, singular_name_short, squad_select, squad_min_play, "
                "squad_max_play, element_count, load_date, run_id) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows
            )
            mark_run_success(cur, run_id, len(rows))
        conn.commit()
        print(f"Inserted {len(rows)} element types into the database.")
        return True
    except Exception as e:
        mark_run_failed(conn, run_id, e)
        if raise_on_error:
            raise
        return False


def main():
    """
    Returns the exit code (0 = everything loaded, 1 = at least one part failed).

    The three loads stay independent: if teams fails, players and element
    types still run (task-level isolation, as before). But the script then
    exits with 1, so the Airflow task turns red. Before, a failed load only
    printed an error and the script exited with 0 - Airflow showed it green.
    """
    data = fetch_json(BOOTSTRAP_URL)
    players = data["elements"]
    teams = data["teams"]
    element_types = data["element_types"]
    events = data["events"]

    # I calculate the snapshot_type ONCE here, not inside the loop - players
    # and teams don't need a different value per item, so I don't want to
    # recalculate the same thing 600+ times for nothing.
    current_snapshot, gw = determine_snapshot_type(events)

    with get_connection() as conn:
        results = [
            ingest_jsonb_entity(conn, "players", "player", players,
                                "bootstrap_static_players", lambda item: current_snapshot),
            ingest_jsonb_entity(conn, "teams", "team", teams,
                                "bootstrap_static_teams", lambda item: current_snapshot),
            ingest_element_types(conn, element_types),
        ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
