from src.db_utils import get_connection


def populate_gold_players(conn):
    """
    Silver to Gold for players - this is where the denormalization decided:
    position and team_name are joined in and stored as readable text,
    instead of keeping raw element_type_id/team_id.
    This keeps dashboard queries simple (no join needed at query time), 
    since players is a small table (~650 rows) where this trade-off is cheap.

    Plain INNER JOIN is safe here (not risky the way it can be elsewhere)
    - silver_players.element_type_id and .team_id both have enforced foreign keys
    back to silver_element_types/silver_teams, so it's structurally impossible 
    for a player to exist with a reference that doesn't resolve.
    No player can silently disappear from this join.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO players (
                player_id,
                web_name,
                position,
                team_name,
                current_price,
                injury_status
            )
            SELECT
                sp.player_id,
                sp.web_name,
                et.singular_name_short AS position,
                st.name                AS team_name,
                sp.current_price,
                sp.injury_status
            FROM silver_players sp
            JOIN silver_element_types et
              ON et.element_type_id = sp.element_type_id
            JOIN silver_teams st
              ON st.team_id = sp.team_id
            ON CONFLICT (player_id) DO UPDATE SET
                web_name      = EXCLUDED.web_name,
                position      = EXCLUDED.position,
                team_name     = EXCLUDED.team_name,
                current_price = EXCLUDED.current_price,
                injury_status = EXCLUDED.injury_status
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Populated {rows_affected} players into Gold players table.")


if __name__ == "__main__":
    conn = get_connection()
    populate_gold_players(conn)
    conn.close()