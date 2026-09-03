import requests
from psycopg.types.json import Jsonb
from datetime import datetime
from src.db_utils import get_connection

response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
data = response.json()
players = data["elements"]
teams = data["teams"]
elements_types = data["element_types"]


def ingest_jsonb_entity(conn, entity_name, singular_name, entity_data):
    """
    Reusable ingestion for JSONB-based Bronze entities (players, teams).
    Not used for element_types, since that table is deliberately flattened
    into typed columns instead of JSONB - different shape, different logic,
    so it gets its own separate function rather than being forced into this one.

    Each call gets its own pipeline_runs row and its own try/except with
    rollback - task-level isolation, so a failure in one entity (e.g. teams)
    never rolls back or blocks an already-successful, more critical entity
    (e.g. players).
    """
    with conn.cursor() as cur:
        cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded)"
            "values (%s, %s, %s, %s) returning run_id",
            (f"bootstrap_static_{entity_name}", datetime.now(), "in_progress", 0)
        )
        run_id = cur.fetchone()[0]
        conn.commit()
    print(f"Pipeline run created with run_id: {run_id}")

    with conn.cursor() as cur:
        try:
            # Jsonb() wraps each raw dict so psycopg correctly serializes it
            # into the raw_json jsonb column. The id is extracted separately
            # for the dedicated {singular_name}_id column.
            #
            # snapshot_type is hardcoded to "post_gameweek" for now - reflects
            # today's actual pipeline state (GW2 finished, GW3 deadline not
            # yet reached).
            # TODO: make this dynamic based on real deadline/gameweek timing
            # once pipeline scheduling logic is built.
            for item in entity_data:
                cur.execute(
                    f"insert into bronze_{entity_name} ({singular_name}_id, raw_json, load_date,"
                    f"snapshot_type, run_id) values (%s, %s, %s, %s, %s)",
                    (item["id"], Jsonb(item), datetime.now(), "post_gameweek", run_id)
                )
            cur.execute(
                "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
                ("success", len(entity_data), run_id)
            )
            conn.commit()
            print(f"Inserted {len(entity_data)} {entity_name} into the database.")
        except Exception as e:
            # rollback undoes all partial inserts from this entity's loop -
            # no half-success state. The pipeline_runs row is then updated
            # with the real error, so failures are visible same-day, not silent.
            conn.rollback()
            print(f"Error occurred: {e}")
            cur.execute(
                "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
                ("failed", str(e), run_id)
            )
            conn.commit()


def ingest_element_types(conn, element_types):
    """
    Separate from ingest_jsonb_entity - bronze_element_types uses individual
    named fields instead of Jsonb(), since this source data is simple and flat
    (no nested structures), making it safe and easy to store in typed columns.
    """
    with conn.cursor() as cur:
        cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded) "
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
                    "insert into bronze_element_types (element_type_id, plural_name, "
                    "singular_name, singular_name_short, squad_select, squad_min_play, "
                    "squad_max_play, element_count, load_date, run_id)"
                    "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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


conn = get_connection()
ingest_jsonb_entity(conn, "players", "player", players)
ingest_jsonb_entity(conn, "teams", "team", teams)
ingest_element_types(conn, elements_types)
conn.close()