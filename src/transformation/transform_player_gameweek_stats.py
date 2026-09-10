from src.db_utils import get_connection


def transform_player_gameweek_stats(conn):
    """
    Bronze to Silver transformation for player gameweek stats.

    This is the only Silver table that joins TWO Bronze sources:
      - bronze_event   -> minutes, goals, assists, clean_sheets,
                          total_points, bonus, bps, xG, xA
                          (from /event/{gw}/live/)
      - bronze_players -> transfers_in_event
                          (from bootstrap-static; this field does NOT
                          exist in the live event endpoint, so it has
                          to come from here)

    bronze_event already has UNIQUE(player_id, gameweek), so it gives
    exactly one row per player per gameweek - no ROW_NUMBER() needed on
    it. bronze_players, on the other hand, holds one snapshot per day,
    so ROW_NUMBER() picks only the latest snapshot per player_id.

    Known limitation (accepted for this project): transfers_in_event here
    is the LATEST value from bronze_players, not the value that was true
    at that exact gameweek. It resets every gameweek on FPL's side.
    Question 4 ("most transferred-in this gameweek") only cares about the
    current gameweek, so the latest value is correct there. For older
    gameweeks, this number may not match what the API showed at the time.
    A stricter design would filter bronze_players by gameweek too - left
    as a future improvement.

    Players flagged by Gate 1 are excluded here, using the latest
    failed_ids from quality_check_results:
      - bronze_event   / required_stats_missing  (incomplete match stats)
      - bronze_players / required_keys_missing   (missing transfers_in_event
                                                  would break the NOT NULL)

    invalid_status_value is NOT used here on purpose - that rule is about
    injury_status, which this table does not store. Only rules that affect
    a column this table actually has are used.

    silver_player_gameweek_stats is APPEND-ONLY (each gameweek is a
    permanent fact, unlike players/teams). ON CONFLICT DO UPDATE makes it
    safe to re-run for the same (player_id, gameweek) without erroring.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver_player_gameweek_stats (
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
                be.player_id,
                be.gameweek,
                lbp.transfers_in_event,
                (be.raw_json->'stats'->>'minutes')::INT              AS minutes,
                (be.raw_json->'stats'->>'goals_scored')::INT         AS goals_scored,
                (be.raw_json->'stats'->>'assists')::INT              AS assists,
                (be.raw_json->'stats'->>'clean_sheets')::INT         AS clean_sheets,
                (be.raw_json->'stats'->>'total_points')::INT         AS total_points,
                (be.raw_json->'stats'->>'bonus')::INT                AS bonus,
                (be.raw_json->'stats'->>'bps')::INT                  AS bps,
                (be.raw_json->'stats'->>'expected_goals')::NUMERIC   AS expected_goals,
                (be.raw_json->'stats'->>'expected_assists')::NUMERIC AS expected_assists,
                be.load_date,
                be.run_id AS source_run_id
            FROM bronze_event be
            JOIN (
                SELECT
                    player_id,
                    (raw_json->>'transfers_in_event')::INT AS transfers_in_event,
                    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY load_date DESC) AS rn
                FROM bronze_players
            ) lbp
              ON lbp.player_id = be.player_id
             AND lbp.rn = 1
            WHERE be.player_id NOT IN (
                (
                    SELECT (jsonb_array_elements(failed_ids))::TEXT::INT
                    FROM quality_check_results
                    WHERE table_name = 'bronze_event'
                      AND rule_name = 'required_stats_missing'
                    ORDER BY checked_at DESC
                    LIMIT 1
                )
                UNION
                (
                    SELECT (jsonb_array_elements(failed_ids))::TEXT::INT
                    FROM quality_check_results
                    WHERE table_name = 'bronze_players'
                      AND rule_name = 'required_keys_missing'
                    ORDER BY checked_at DESC
                    LIMIT 1
                )
            )
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
    print(f"Transformed and upserted {rows_affected} player gameweek stats into silver_player_gameweek_stats.")


if __name__ == "__main__":
    conn = get_connection()
    transform_player_gameweek_stats(conn)
    conn.close()