from src.db_utils import get_connection
from src.quality_checks.quality_utils import run_quality_check


def check_bronze_fixtures(conn):
    """
    Two separate rules for bronze_fixtures, instead of one combined check:

    1. required_keys_missing - fields that should exist on EVERY fixture,
       played or not (id, event, kickoff_time, team_h, team_a, difficulty).

    2. finished_match_missing_scores - score fields only make sense to
       check on fixtures that are actually finished. An unplayed fixture
       legitimately has null scores - that's not a bug, that's just a
       match that hasn't happened yet. Checking scores across ALL fixtures
       would wrongly flag every future fixture as broken, so this rule
       only runs against fixtures where finished = true.
    """
    run_quality_check(
        conn,
        table_name="bronze_fixtures",
        rule_name="required_keys_missing",
        count_query="SELECT COUNT(*) FROM bronze_fixtures",
        failed_ids_query="""
            SELECT fixture_id
            FROM bronze_fixtures
            WHERE raw_json->>'id' IS NULL
               OR raw_json->>'event' IS NULL
               OR raw_json->>'kickoff_time' IS NULL
               OR raw_json->>'team_h' IS NULL
               OR raw_json->>'team_a' IS NULL
               OR raw_json->>'team_h_difficulty' IS NULL
               OR raw_json->>'team_a_difficulty' IS NULL
        """
    )

    run_quality_check(
        conn,
        table_name="bronze_fixtures",
        rule_name="finished_match_missing_scores",
        count_query="""
            SELECT COUNT(*) FROM bronze_fixtures
            WHERE (raw_json->>'finished')::boolean = true
        """,
        failed_ids_query="""
            SELECT fixture_id
            FROM bronze_fixtures
            WHERE (raw_json->>'finished')::boolean = true
              AND (raw_json->>'team_h_score' IS NULL
                   OR raw_json->>'team_a_score' IS NULL)
        """
    )


if __name__ == "__main__":
    conn = get_connection()
    check_bronze_fixtures(conn)
    conn.close()