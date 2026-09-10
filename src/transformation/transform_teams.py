from src.db_utils import get_connection


def transform_teams(conn):
    """
    Bronze to Silver transformation for teams. Simpler than players - no
    value conversions or translations needed, just extraction and type
    casting, since every field maps directly to a Silver column.

    Same pattern as transform_players: ROW_NUMBER() picks the latest
    snapshot per team_id, teams flagged by Gate 1 (required_keys_missing)
    are excluded, and ON CONFLICT DO UPDATE keeps this safe to run
    repeatedly (overwrite pattern, one row per team).

    Known limitation: FPL's own points/played/position/win/draw/loss
    fields for teams have been observed staying at 0 even well into the
    season - this looks like a quirk on FPL's side, not a bug in this
    pipeline. None of the 6 dashboard questions this project answers
    depend on these fields being accurate (teams exists mainly for
    name/short_name context), so this is accepted as-is for now.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver_teams (
                team_id, name, short_name, points, played, position, win,
                draw, loss, load_date, source_run_id
            )
            SELECT
                t.team_id,
                t.raw_json->>'name' AS name,
                t.raw_json->>'short_name' AS short_name,
                (t.raw_json->>'points')::INT AS points,
                (t.raw_json->>'played')::INT AS played,
                (t.raw_json->>'position')::INT AS position,
                (t.raw_json->>'win')::INT AS win,
                (t.raw_json->>'draw')::INT AS draw,
                (t.raw_json->>'loss')::INT AS loss,
                t.load_date,
                t.run_id AS source_run_id
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY load_date DESC) AS rn
                FROM bronze_teams
            ) t
            WHERE t.rn = 1
              AND t.team_id NOT IN (
                  SELECT jsonb_array_elements(failed_ids)::TEXT::INT
                  FROM quality_check_results
                  WHERE table_name = 'bronze_teams'
                    AND rule_name = 'required_keys_missing'
                  ORDER BY checked_at DESC
                  LIMIT 1
              )
            ON CONFLICT (team_id) DO UPDATE SET
                name          = EXCLUDED.name,
                short_name    = EXCLUDED.short_name,
                points        = EXCLUDED.points,
                played        = EXCLUDED.played,
                position      = EXCLUDED.position,
                win           = EXCLUDED.win,
                draw          = EXCLUDED.draw,
                loss          = EXCLUDED.loss,
                load_date     = EXCLUDED.load_date,
                source_run_id = EXCLUDED.source_run_id
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Transformed and upserted {rows_affected} teams into silver_teams.")


if __name__ == "__main__":
    conn = get_connection()
    transform_teams(conn)
    conn.close()