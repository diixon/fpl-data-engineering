from src.db_utils import get_connection
from src.quality_checks.quality_utils import run_quality_check


def check_bronze_players(conn):
    """
    Two rules for bronze_players:

    1. required_keys_missing - my table's own constraints (NOT NULL,
       foreign keys) only protect the outer shape of a row. They cannot
       see INSIDE the raw_json blob. If the FPL API ever sent a player
       missing a field like now_cost, my table would insert it fine, with
       no error at all. This rule catches that gap.

    2. invalid_status_value - even when 'status' exists, its value might
       not be one of the 5 codes I actually know how to translate ('a',
       'i', 'd', 's', 'u'). My Silver transformation maps unknown codes to
       'unknown' on purpose, instead of silently guessing a default - so
       this rule flags them here in Bronze, where I can actually notice
       and investigate, rather than letting a bad code get silently
       mislabeled downstream.
    """
    run_quality_check(
        conn,
        table_name="bronze_players",
        rule_name="required_keys_missing",
        count_query="SELECT COUNT(*) FROM bronze_players",
        failed_ids_query="""
            SELECT player_id
            FROM bronze_players
            WHERE raw_json->>'id' IS NULL
               OR raw_json->>'web_name' IS NULL
               OR raw_json->>'element_type' IS NULL
               OR raw_json->>'team' IS NULL
               OR raw_json->>'now_cost' IS NULL
               OR raw_json->>'status' IS NULL
        """
    )

    run_quality_check(
        conn,
        table_name="bronze_players",
        rule_name="invalid_status_value",
        count_query="SELECT COUNT(*) FROM bronze_players",
        failed_ids_query="""
            SELECT player_id
            FROM bronze_players
            WHERE raw_json->>'status' NOT IN ('a', 'i', 'd', 's', 'u')
        """
    )


if __name__ == "__main__":
    conn = get_connection()
    check_bronze_players(conn)
    conn.close()