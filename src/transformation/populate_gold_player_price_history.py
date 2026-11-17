from src.db_utils import get_connection, fetch_json, latest_failed_ids_sql


def get_current_gameweek(events):
    """
    Returns the current gameweek's id, using FPL's own is_current flag -
    separate from determine_snapshot_type, which only returns a gameweek
    number once a gameweek is finished. Price changes can happen any day,
    not just post-gameweek, so this needs the CURRENT gameweek, whatever
    state it's in.
    """
    for event in events:
        if event["is_current"]:
            return event["id"]
    # Without this, the function silently returned None and the INSERT
    # later failed with a confusing NULL-in-primary-key error.
    raise ValueError("No gameweek has is_current = true in the FPL events data.")


def populate_gold_player_price_history(conn, gameweek):
    """
    Silver to Gold for player price history. Unlike the other Gold
    tables, this reads directly from bronze_players, not Silver - Silver
    only keeps current_price (today's snapshot), not the raw
    cost_change_event field needed to detect an actual price movement.

    cost_change_event accumulates across the whole current gameweek and
    resets when a new gameweek starts (same relationship cost_change_start
    has to the whole season, based on FPL's own naming pattern - not
    confirmed by official documentation, but a reasonable, documented
    assumption). Taking the LATEST snapshot within a gameweek (ROW_NUMBER)
    therefore already gives the combined net change for that week, with
    no need to manually sum multiple days.

    Grain: one row per player per gameweek, and ONLY when a real change
    happened (cost_change_event != 0). A player whose price never changes
    simply has zero rows - that's the correct, honest state, not a gap.

    old_price is not stored, since it's always derivable: new_price -
    price_change_amount reconstructs it, so storing it separately would
    be redundant.

    Two protections added after testing: (1) JOIN players - this table has
    a foreign key to Gold players, and a player that Silver left out
    (Gate 1) is not in Gold players, so without the JOIN one such player
    crashed the whole load. (2) Gate 1 required_keys_missing ids are
    skipped, because this query reads Bronze directly and would otherwise
    hit a NOT NULL error on a missing now_cost.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO player_price_history (
                player_id,
                gameweek,
                new_price,
                price_change_amount,
                load_date,
                source_run_id
            )
            SELECT
                t.player_id,
                %s AS gameweek,
                (t.raw_json->>'now_cost')::NUMERIC / 10.0          AS new_price,
                (t.raw_json->>'cost_change_event')::NUMERIC / 10.0 AS price_change_amount,
                t.load_date,
                t.run_id AS source_run_id
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY load_date DESC) AS rn
                FROM bronze_players
            ) t
            JOIN players p
              ON p.player_id = t.player_id
            WHERE t.rn = 1
              AND (t.raw_json->>'cost_change_event')::INT != 0
              AND t.player_id NOT IN (
                  {latest_failed_ids_sql('bronze_players', 'required_keys_missing')}
              )
            ON CONFLICT (player_id, gameweek) DO UPDATE SET
                new_price           = EXCLUDED.new_price,
                price_change_amount = EXCLUDED.price_change_amount,
                load_date           = EXCLUDED.load_date,
                source_run_id       = EXCLUDED.source_run_id
            """,
            (gameweek,)
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Populated {rows_affected} price changes into Gold player_price_history (gameweek {gameweek}).")


if __name__ == "__main__":
    events = fetch_json("https://fantasy.premierleague.com/api/bootstrap-static/")["events"]
    gw = get_current_gameweek(events)

    with get_connection() as conn:
        populate_gold_player_price_history(conn, gw)