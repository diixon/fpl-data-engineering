from src.db_utils import get_connection, latest_failed_ids_sql


def transform_players(conn):
    """
    Bronze to Silver transformation for players.

    bronze_players can hold multiple snapshots per player (one row per
    ingestion run), so ROW_NUMBER() picks only the most recent one per
    player_id, ordered by load_date.

    Players flagged by Gate 1 (required_keys_missing or invalid_status_value)
    are excluded here, using the latest failed_ids from quality_check_results
    for each rule. This is the "skip and log" policy decided earlier: bad
    rows don't block the whole transformation, they're just left out until
    the underlying data issue is understood.

    now_cost is converted from a raw integer (e.g. 60) into a real price
    (6.0). status is translated from FPL's single-letter codes into full
    words. Any status code outside the 5 known values maps to 'unknown'
    on purpose, instead of silently guessing a default - this makes an
    unexpected code visible (it fails the CHECK constraint) rather than
    hiding it as if it were a normal value.

    silver_players is an overwrite table - one row per player, no history.
    ON CONFLICT DO UPDATE makes this safe to run again and again, updating
    existing players instead of erroring on duplicate player_id.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO silver_players (
                player_id,
                web_name,
                element_type_id,
                team_id,
                current_price,
                injury_status,
                load_date,
                source_run_id
            )
            SELECT
                t.player_id,
                t.raw_json->>'web_name' AS web_name,
                (t.raw_json->>'element_type')::INT AS element_type_id,
                (t.raw_json->>'team')::INT AS team_id,
                (t.raw_json->>'now_cost')::NUMERIC / 10.0 AS current_price,
                CASE
                    WHEN t.raw_json->>'status' = 'a' THEN 'available'
                    WHEN t.raw_json->>'status' = 'd' THEN 'doubtful'
                    WHEN t.raw_json->>'status' = 'i' THEN 'injured'
                    WHEN t.raw_json->>'status' = 's' THEN 'suspended'
                    WHEN t.raw_json->>'status' = 'u' THEN 'unavailable'
                    ELSE 'unknown'
                END AS injury_status,
                t.load_date,
                t.run_id AS source_run_id
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY load_date DESC) AS rn
                FROM bronze_players
            ) t
            WHERE t.rn = 1
              AND t.player_id NOT IN (
                  {latest_failed_ids_sql('bronze_players', 'required_keys_missing')}
                  UNION
                  {latest_failed_ids_sql('bronze_players', 'invalid_status_value')}
              )
            ON CONFLICT (player_id) DO UPDATE SET
                web_name        = EXCLUDED.web_name,
                element_type_id = EXCLUDED.element_type_id,
                team_id         = EXCLUDED.team_id,
                current_price   = EXCLUDED.current_price,
                injury_status   = EXCLUDED.injury_status,
                load_date       = EXCLUDED.load_date,
                source_run_id   = EXCLUDED.source_run_id
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Transformed and upserted {rows_affected} players into silver_players.")


if __name__ == "__main__":
    with get_connection() as conn:
        transform_players(conn)