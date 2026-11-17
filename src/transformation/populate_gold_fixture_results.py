from src.db_utils import get_connection


def populate_gold_fixture_results(conn):
    """
    Silver to Gold for fixture results - denormalized team names, same
    reasoning as players: small table (~380 rows/season), cheap to
    denormalize, speeds up dashboard queries.

    silver_teams is joined TWICE with different aliases (sth, sta) -
    once for the home team, once for the away team - since both team
    names need to be looked up from the same source table for each
    fixture.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fixture_results (
                fixture_id,
                gameweek,
                kickoff_time,
                team_h_name,
                team_a_name,
                team_h_score,
                team_a_score,
                team_h_difficulty,
                team_a_difficulty,
                load_date,
                source_run_id
            )
            SELECT
                sf.fixture_id,
                sf.gameweek,
                sf.kickoff_time,
                sth.name AS team_h_name,
                sta.name AS team_a_name,
                sf.team_h_score,
                sf.team_a_score,
                sf.team_h_difficulty,
                sf.team_a_difficulty,
                sf.load_date,
                sf.source_run_id
            FROM silver_fixtures sf
            JOIN silver_teams sth
              ON sth.team_id = sf.team_h
            JOIN silver_teams sta
              ON sta.team_id = sf.team_a
            ON CONFLICT (fixture_id) DO UPDATE SET
                gameweek          = EXCLUDED.gameweek,
                kickoff_time      = EXCLUDED.kickoff_time,
                team_h_name       = EXCLUDED.team_h_name,
                team_a_name       = EXCLUDED.team_a_name,
                team_h_score      = EXCLUDED.team_h_score,
                team_a_score      = EXCLUDED.team_a_score,
                team_h_difficulty = EXCLUDED.team_h_difficulty,
                team_a_difficulty = EXCLUDED.team_a_difficulty,
                load_date         = EXCLUDED.load_date,
                source_run_id     = EXCLUDED.source_run_id
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Populated {rows_affected} fixture results into Gold fixture_results.")


if __name__ == "__main__":
    with get_connection() as conn:
        populate_gold_fixture_results(conn)