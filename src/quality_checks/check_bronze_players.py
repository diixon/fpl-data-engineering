from src.db_utils import get_connection
from src.quality_checks.quality_utils import run_quality_check


def check_bronze_players(conn):
    """
    Gate 1 check for bronze_players. My table's own constraints (NOT NULL,
    foreign keys) only protect the outer shape of each row - player_id
    exists, raw_json exists, run_id is valid. They cannot see INSIDE the
    raw_json blob. If the FPL API ever sent a player missing a field like
    now_cost, my table would insert it fine, with no error at all.

    This check looks inside raw_json for the fields Silver actually needs
    later (id, web_name, element_type, team, now_cost, status) - catching
    a problem here, right when it enters Bronze, instead of finding out
    later when Silver's conversion logic breaks or produces garbage.
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


if __name__ == "__main__":
    conn = get_connection()
    check_bronze_players(conn)
    conn.close()