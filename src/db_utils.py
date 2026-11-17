"""
db_utils.py - shared database connection and shared ingestion logic.

I keep this separate from any single ingestion script, because every part
of the pipeline (ingestion, quality checks, transformation) needs to connect
to Postgres and reuse the same JSONB ingestion pattern. I write it once here,
and import it everywhere else, instead of repeating the same code.
"""

import os
import psycopg
import requests
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
    print("Connected successfully!")
    return conn


def fetch_json(url):
    """
    One place for every FPL API call. Two things the plain requests.get
    did not do: timeout (without it, a stuck connection can hang the
    Airflow task forever) and raise_for_status (without it, an HTTP 500
    or 403 page would be parsed as if it were data and fail later with a
    confusing error far from the real cause).
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def start_pipeline_run(conn, source_name):
    """Creates the pipeline_runs row for one ingestion attempt and returns its run_id."""
    with conn.cursor() as cur:
        cur.execute(
            "insert into pipeline_runs (source_name, run_timestamp, status, rows_loaded) "
            "values (%s, %s, %s, %s) returning run_id",
            (source_name, datetime.now(), "in_progress", 0)
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    print(f"Pipeline run created with run_id: {run_id}")
    return run_id


def mark_run_success(cur, run_id, rows_loaded):
    """
    Takes a CURSOR (not a connection) and does not commit on purpose: the
    caller commits once, so the inserted rows and the 'success' status are
    saved together or not at all.
    """
    cur.execute(
        "update pipeline_runs set status = %s, rows_loaded = %s where run_id = %s",
        ("success", rows_loaded, run_id)
    )


def mark_run_failed(conn, run_id, error):
    """
    rollback undoes all partial inserts - no half success state. Then the
    real error is saved in pipeline_runs, so I can see failures the same
    day, not find out later.
    """
    conn.rollback()
    print(f"Error occurred: {error}")
    with conn.cursor() as cur:
        cur.execute(
            "update pipeline_runs set status = %s, error_message = %s where run_id = %s",
            ("failed", str(error), run_id)
        )
    conn.commit()


def latest_failed_ids_sql(table_name, rule_name):
    """
    Returns a SQL snippet that gives back the failed IDs from the LATEST
    Gate 1 check of one rule, one ID per row. The transform scripts put it
    inside "NOT IN (...)" to skip the rows Gate 1 flagged.

    Why this is a function: the same exclusion logic is needed in several
    transform scripts, so I write it once here (DRY).

    Why the nested subquery matters: the first version used
        SELECT jsonb_array_elements(failed_ids) ... ORDER BY checked_at DESC LIMIT 1
    but in Postgres the set-returning function expands the array into rows
    BEFORE ORDER BY / LIMIT run - so LIMIT 1 kept only ONE failed ID, not
    the whole list of the latest check. The inner query picks the latest
    check row first (LIMIT 1 on whole rows), and only then the outer query
    expands its failed_ids array. I tested both versions: with 5 failed IDs
    the old one excluded 1, this one excludes all 5.

    table_name and rule_name are fixed strings written in my own code
    (never user input), so putting them in the SQL text is safe here.
    """
    return f"""
        SELECT jsonb_array_elements_text(latest.failed_ids)::INT
        FROM (
            SELECT failed_ids
            FROM quality_check_results
            WHERE table_name = '{table_name}'
              AND rule_name = '{rule_name}'
            ORDER BY checked_at DESC
            LIMIT 1
        ) latest
    """


def ingest_jsonb_entity(conn, entity_name, singular_name, entity_data,
                         source_name, get_snapshot_type, raise_on_error=False):
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

    Return value / raise_on_error: the function returns True on success and
    False on failure, so the caller can know what happened. By default a
    failure is recorded in pipeline_runs and NOT raised (keeps the isolation
    above). Under Airflow a task that swallows its error shows up green, so
    the ingestion scripts check the return value and exit with code 1.
    """
    run_id = start_pipeline_run(conn, source_name)

    try:
        # One load time for the whole run (instead of one per row), so every
        # row from the same run is easy to group by load_date.
        load_time = datetime.now()

        # Jsonb() wraps each raw dict so psycopg saves it correctly into
        # the raw_json jsonb column. The id is taken out separately for
        # the dedicated {singular_name}_id column. I build the full list
        # first, then insert it with executemany - one batch instead of one
        # round trip per row (same lesson as the SuperStore project).
        rows = [
            (item["id"], Jsonb(item), load_time, get_snapshot_type(item), run_id)
            for item in entity_data
        ]
        with conn.cursor() as cur:
            cur.executemany(
                f"insert into bronze_{entity_name} ({singular_name}_id, raw_json, load_date, "
                f"snapshot_type, run_id) values (%s, %s, %s, %s, %s)",
                rows
            )
            mark_run_success(cur, run_id, len(rows))
        conn.commit()
        print(f"Inserted {len(rows)} {entity_name} into the database.")
        return True
    except Exception as e:
        mark_run_failed(conn, run_id, e)
        if raise_on_error:
            raise
        return False


def _parse_deadline(event):
    """FPL sends deadlines like '2026-08-15T17:30:00Z'; Python needs '+00:00' instead of 'Z'."""
    return datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))


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

    If no branch matches (for example before the season starts, when no
    deadline is in the past yet), the old version fell off the end and
    returned None, and the caller's "label, gw = ..." crashed with
    "cannot unpack non-iterable NoneType". Now it raises a clear error.
    """
    now = datetime.now(timezone.utc)
    future_events = [e for e in events if _parse_deadline(e) > now]
    if future_events:
        next_event = min(future_events, key=_parse_deadline)
        if _parse_deadline(next_event).date() == now.date():
            return "deadline", None
    past_events = [e for e in events if _parse_deadline(e) <= now]
    if past_events:
        latest_event = max(past_events, key=_parse_deadline)
        if latest_event['finished']:
            return "post_gameweek", latest_event['id']
        return "live", None
    raise ValueError(
        "Could not determine snapshot type: no gameweek deadline has passed yet "
        "(is the season not started?)"
    )


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
