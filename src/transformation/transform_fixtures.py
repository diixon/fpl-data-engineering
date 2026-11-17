from src.db_utils import get_connection, latest_failed_ids_sql


def transform_fixtures(conn):
    """
    Bronze to Silver transformation for fixtures. Only finished matches
    are transformed - the finished = true filter is applied INSIDE the
    ROW_NUMBER() subquery, before ranking, not after. This matters: a
    fixture can have multiple snapshots (pre_match, live, post_match).
    If unfinished snapshots were included before ranking, a live snapshot
    could accidentally rank as "most recent" over a real post_match
    snapshot, even though the finished version exists. Filtering first
    guarantees rn = 1 only ever picks among already-finished snapshots.

    Two Gate 1 rules are combined with UNION for the exclusion list:
    required_keys_missing and finished_match_missing_scores - a fixture
    flagged by either rule is excluded from this run.

    Same overwrite pattern as players/teams: ON CONFLICT DO UPDATE keeps
    this safe to run repeatedly.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO silver_fixtures (
                fixture_id, gameweek, kickoff_time,
                team_h, team_a, team_h_score, team_a_score,
                team_h_difficulty, team_a_difficulty,
                load_date, source_run_id
            )
            SELECT
                t.fixture_id,
                (t.raw_json->>'event')::INT AS gameweek,
                (t.raw_json->>'kickoff_time')::TIMESTAMPTZ AS kickoff_time,
                (t.raw_json->>'team_h')::INT AS team_h,
                (t.raw_json->>'team_a')::INT AS team_a,
                (t.raw_json->>'team_h_score')::INT AS team_h_score,
                (t.raw_json->>'team_a_score')::INT AS team_a_score,
                (t.raw_json->>'team_h_difficulty')::INT AS team_h_difficulty,
                (t.raw_json->>'team_a_difficulty')::INT AS team_a_difficulty,
                t.load_date,
                t.run_id AS source_run_id
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY fixture_id ORDER BY load_date DESC) AS rn
                FROM bronze_fixtures
                WHERE (raw_json->>'finished')::boolean = true
            ) t
            WHERE t.rn = 1
              AND t.fixture_id NOT IN (
                  {latest_failed_ids_sql('bronze_fixtures', 'required_keys_missing')}
                  UNION
                  {latest_failed_ids_sql('bronze_fixtures', 'finished_match_missing_scores')}
              )
            ON CONFLICT (fixture_id) DO UPDATE SET
                gameweek            = EXCLUDED.gameweek,
                kickoff_time        = EXCLUDED.kickoff_time,
                team_h              = EXCLUDED.team_h,
                team_a              = EXCLUDED.team_a,
                team_h_score        = EXCLUDED.team_h_score,
                team_a_score        = EXCLUDED.team_a_score,
                team_h_difficulty   = EXCLUDED.team_h_difficulty,
                team_a_difficulty   = EXCLUDED.team_a_difficulty,
                load_date           = EXCLUDED.load_date,
                source_run_id       = EXCLUDED.source_run_id
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Transformed and upserted {rows_affected} fixtures into silver_fixtures.")


if __name__ == "__main__":
    with get_connection() as conn:
        transform_fixtures(conn)