from src.db_utils import get_connection


def populate_gold_player_gameweek_performance(conn):
    """
    Silver to Gold for player gameweek performance - a direct copy, no
    joins. Kept normalized on purpose (no web_name denormalized here),
    unlike the players table - this is an append-only fact table that
    grows every gameweek (~650 players x 38 gameweeks = 20,000+ rows a
    season), so denormalizing would multiply storage cost for a table
    this size, unlike the small players dimension table where that
    trade-off is cheap.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO player_gameweek_performance (
                player_id,
                gameweek,
                transfers_in_event,
                minutes,
                goals_scored,
                assists,
                clean_sheets,
                total_points,
                bonus,
                bps,
                expected_goals,
                expected_assists,
                load_date,
                source_run_id
            )
            SELECT
                player_id,
                gameweek,
                transfers_in_event,
                minutes,
                goals_scored,
                assists,
                clean_sheets,
                total_points,
                bonus,
                bps,
                expected_goals,
                expected_assists,
                load_date,
                source_run_id
            FROM silver_player_gameweek_stats
            ON CONFLICT (player_id, gameweek) DO UPDATE SET
                transfers_in_event = EXCLUDED.transfers_in_event,
                minutes            = EXCLUDED.minutes,
                goals_scored       = EXCLUDED.goals_scored,
                assists            = EXCLUDED.assists,
                clean_sheets       = EXCLUDED.clean_sheets,
                total_points       = EXCLUDED.total_points,
                bonus              = EXCLUDED.bonus,
                bps                = EXCLUDED.bps,
                expected_goals     = EXCLUDED.expected_goals,
                expected_assists   = EXCLUDED.expected_assists,
                load_date          = EXCLUDED.load_date,
                source_run_id      = EXCLUDED.source_run_id
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Populated {rows_affected} rows into Gold player_gameweek_performance.")


if __name__ == "__main__":
    conn = get_connection()
    populate_gold_player_gameweek_performance(conn)
    conn.close()