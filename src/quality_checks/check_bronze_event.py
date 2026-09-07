from src.db_utils import get_connection
from src.quality_checks.quality_utils import run_quality_check


def check_bronze_event(conn):
    """
    Gate 1 check for bronze_event. Unlike players/teams/fixtures, the stats
    Silver needs are nested one level deeper, inside raw_json->'stats',
    not at the top level - so the check reaches into that nested object
    (raw_json->'stats'->>'field') instead of raw_json->>'field' directly.

    gameweek itself isn't checked here, since it's a real column with its
    own NOT NULL constraint already enforced by the table - Gate 1 only
    needs to check what's invisible to the database, inside raw_json.
    """
    run_quality_check(
        conn,
        table_name="bronze_event",
        rule_name="required_stats_missing",
        count_query="SELECT COUNT(*) FROM bronze_event",
        failed_ids_query="""
            SELECT player_id
            FROM bronze_event
            WHERE raw_json->>'id' IS NULL
               OR raw_json->'stats'->>'transfers_in_event' IS NULL
               OR raw_json->'stats'->>'minutes' IS NULL
               OR raw_json->'stats'->>'goals_scored' IS NULL
               OR raw_json->'stats'->>'assists' IS NULL
               OR raw_json->'stats'->>'clean_sheets' IS NULL
               OR raw_json->'stats'->>'total_points' IS NULL
               OR raw_json->'stats'->>'bonus' IS NULL
               OR raw_json->'stats'->>'bps' IS NULL
               OR raw_json->'stats'->>'expected_goals' IS NULL
               OR raw_json->'stats'->>'expected_assists' IS NULL
        """
    )


if __name__ == "__main__":
    conn = get_connection()
    check_bronze_event(conn)
    conn.close()