from src.db_utils import get_connection
from src.quality_checks.quality_utils import run_quality_check


def check_bronze_teams(conn):
    """
    One rule for bronze_teams - unlike fixtures, no conditional split is
    needed here. Fields like points/played/win/draw/loss are always
    present and default to 0 at the start of the season - 0 is a real,
    valid value, not a sign of missing data. So this check applies to
    every team, every time, with no exceptions.
    """
    run_quality_check(
        conn,
        table_name="bronze_teams",
        rule_name="required_keys_missing",
        count_query="SELECT COUNT(*) FROM bronze_teams",
        failed_ids_query="""
            SELECT team_id
            FROM bronze_teams
            WHERE raw_json->>'id' IS NULL
               OR raw_json->>'name' IS NULL
               OR raw_json->>'short_name' IS NULL
               OR raw_json->>'points' IS NULL
               OR raw_json->>'played' IS NULL
               OR raw_json->>'position' IS NULL
               OR raw_json->>'win' IS NULL
               OR raw_json->>'draw' IS NULL
               OR raw_json->>'loss' IS NULL
        """
    )


if __name__ == "__main__":
    conn = get_connection()
    check_bronze_teams(conn)
    conn.close()