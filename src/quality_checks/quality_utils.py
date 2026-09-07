"""
quality_utils.py - shared logic for Gate 1 quality checks.

Same idea as db_utils.py: every quality check follows the same shape - run
a query, count how many rows failed, record the result. I write that shape
once here, and each table-specific check script just supplies its own
table_name, rule_name, and the two SQL queries it needs.
"""

from datetime import datetime, timezone
from psycopg.types.json import Jsonb


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
    print(f"[{table_name} / {rule_name}] Checked {rows_checked} rows — {rows_failed} failed.")
