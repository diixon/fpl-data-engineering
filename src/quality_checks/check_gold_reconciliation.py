from src.db_utils import get_connection
from src.quality_checks.quality_utils import run_quality_check


def check_gold_reconciliation(conn):
    """
    Gate 2 check - catches ONE specific class of bug: rows silently
    disappearing during Silver to Gold transformation (e.g. a wrong JOIN
    condition dropping rows that should have matched). This does NOT
    catch every possible transformation bug - a bug like a home/away team
    swap, or any mistake that keeps the row count the same but changes
    the actual values, would NOT be caught by this check. That kind of
    bug requires carefully testing the transformation query itself when
    it's written, not an automated row-count check.

    Compares row counts between each Silver source and its direct-copy
    Gold target. They should always be equal, since none of these four
    transformations intentionally filter anything out (unlike Bronze to
    Silver, which does exclude Gate 1 failures and unfinished fixtures -
    Silver's output is already the "clean" set, so Gold should carry
    every row forward).

    player_price_history is intentionally excluded from this check - its
    row count is NOT expected to equal any Silver table, since its grain
    is "one row per price change event", not a direct copy. A different
    check would be needed for that table, not built here.

    Reuses quality_check_results rather than a new table - rows_checked
    is Silver's count, rows_failed is the row-count difference (how many
    are missing, not which ones), failed_ids is left NULL since specific
    missing rows aren't identified here, only the fact that some are
    missing.
    """
    reconciliation_pairs = [
        ("silver_teams", "teams"),
        ("silver_players", "players"),
        ("silver_fixtures", "fixture_results"),
        ("silver_player_gameweek_stats", "player_gameweek_performance"),
    ]

    for silver_table, gold_table in reconciliation_pairs:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {silver_table}")
            silver_count = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM {gold_table}")
            gold_count = cur.fetchone()[0]

        rows_failed = max(silver_count - gold_count, 0)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO quality_check_results
                    (table_name, rule_name, checked_at, rows_checked,
                     rows_failed, failed_ids)
                VALUES
                    (%s, %s, NOW(), %s, %s, NULL)
                """,
                (
                    gold_table,
                    "silver_gold_row_count_mismatch",
                    silver_count,
                    rows_failed
                )
            )
        conn.commit()

        print(f"[{gold_table}] Silver: {silver_count}, Gold: {gold_count} — "
              f"{'OK' if rows_failed == 0 else f'{rows_failed} rows missing'}")


if __name__ == "__main__":
    conn = get_connection()
    check_gold_reconciliation(conn)
    conn.close()