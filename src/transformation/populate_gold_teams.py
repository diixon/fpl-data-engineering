from src.db_utils import get_connection


def populate_gold_teams(conn):
    """
    Silver to Gold for teams - a simple, direct copy. No deduplication
    needed (silver_teams already guarantees one row per team_id), and no
    Gate 1 exclusion needed (that filtering already happened once, when
    Bronze was transformed into Silver - Gold trusts Silver's output).

    Same overwrite pattern as Silver: ON CONFLICT DO UPDATE keeps this
    safe to re-run.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO teams (team_id, name, short_name)
            SELECT
                team_id,
                name,
                short_name
            FROM silver_teams
            ON CONFLICT (team_id) DO UPDATE SET
                name       = EXCLUDED.name,
                short_name = EXCLUDED.short_name
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Populated {rows_affected} teams into Gold teams table.")


if __name__ == "__main__":
    conn = get_connection()
    populate_gold_teams(conn)
    conn.close()