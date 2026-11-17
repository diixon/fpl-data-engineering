"""
quality_utils.py - shared logic for Gate 1 and Gate 2 quality checks.

Same idea as db_utils.py: every quality check follows the same shape - run
a query, count how many rows failed, record the result. I write that shape
once here, and each table-specific check script just supplies its own
table_name, rule_name, and the two SQL queries it needs.
"""

from datetime import datetime, timezone
from psycopg.types.json import Jsonb


def latest_snapshot_sql(table_name, id_column):
    """
    Returns a SQL snippet (a sub-select with alias "latest") that keeps only
    the NEWEST snapshot of each entity in a Bronze table.

    Why Gate 1 looks only at the newest snapshot: the Silver transformation
    only ever uses the newest snapshot per id (ROW_NUMBER ... rn = 1). The
    first version of Gate 1 checked EVERY row ever loaded, so one bad old
    snapshot (for example a player missing now_cost five days ago) kept that
    id on the failed list forever - and Silver then skipped the player even
    though today's snapshot was perfectly fine. A check should judge the
    same rows that Silver is going to use.

    table_name and id_column are fixed strings from my own code, not user input.
    """
    return f"""(
        SELECT * FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY {id_column} ORDER BY load_date DESC) AS rn
            FROM {table_name}
        ) ranked
        WHERE rn = 1
    ) latest"""


def record_check_result(conn, table_name, rule_name, rows_checked, rows_failed,
                        failed_ids=None):
    """
    The one place that INSERTs into quality_check_results. Both Gate 1
    (run_quality_check below) and Gate 2 (check_gold_reconciliation) use it,
    so the timestamp (always UTC from Python) and the failed_ids handling
    are the same everywhere.

    failed_ids stays NULL when nothing failed, or when the check only knows
    HOW MANY rows are missing, not which ones (Gate 2).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO quality_check_results
                (table_name, rule_name, checked_at, rows_checked,
                 rows_failed, failed_ids)
            VALUES
                (%s, %s, %s, %s, %s, %s)
            """,
            (
                table_name,
                rule_name,
                datetime.now(timezone.utc),
                rows_checked,
                rows_failed,
                Jsonb(failed_ids) if failed_ids is not None else None
            )
        )
    conn.commit()


def run_quality_check(conn, table_name, rule_name, count_query, failed_ids_query):
    """
    Runs one quality rule against one table, and saves the result into
    quality_check_results.

    count_query - counts the total rows this rule applies to.
    failed_ids_query - returns the ids of the rows that failed this rule.

    I keep failed_ids as a real JSONB list (not just a count), because a
    count alone is not useful - I need the actual ids if I ever want to
    go back and look at which specific rows are broken.

    This table does NOT link to one specific pipeline_runs.run_id, on
    purpose. A quality check looks at the whole table, which usually holds
    data from many different ingestion runs mixed together, not just one -
    so pointing to a single run_id would be misleading. checked_at is
    enough to know when the check happened.
    """
    with conn.cursor() as cur:
        cur.execute(count_query)
        rows_checked = cur.fetchone()[0]

        cur.execute(failed_ids_query)
        failed_rows = cur.fetchall()

    rows_failed = len(failed_rows)
    failed_ids = [row[0] for row in failed_rows] if failed_rows else None

    record_check_result(conn, table_name, rule_name, rows_checked, rows_failed, failed_ids)
    print(f"[{table_name} / {rule_name}] Checked {rows_checked} rows — {rows_failed} failed.")
