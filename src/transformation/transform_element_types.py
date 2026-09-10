from src.db_utils import get_connection


def transform_element_types(conn):
    """
    Bronze to Silver transformation for element_types. Unlike the other
    three transformations, no raw_json extraction is needed here - Bronze
    already stores this data as real, typed columns (flattened), since
    this table was designed without JSONB from the start.

    No Gate 1 exclusion either - this table has no quality check, since
    its NOT NULL constraints already guarantee everything a check would
    verify (there's no hidden JSON blob where a problem could hide).

    ROW_NUMBER() is still needed though - bronze_element_types gets a
    fresh row inserted every day (it's pulled in the same call as players
    and teams), so multiple rows accumulate per element_type_id over time.
    Testing confirmed that ON CONFLICT DO UPDATE alone is NOT enough here:
    it only protects against conflicts with rows already saved from a
    previous statement - it errors out if the SAME INSERT's own SELECT
    tries to insert the same key twice in one go. ROW_NUMBER() prevents
    that by narrowing the SELECT down to exactly one row per
    element_type_id before the INSERT ever runs.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver_element_types (
                element_type_id,
                plural_name,
                singular_name,
                singular_name_short,
                squad_select,
                squad_min_play,
                squad_max_play,
                element_count,
                load_date,
                source_run_id
            )
            SELECT
                t.element_type_id,
                t.plural_name,
                t.singular_name,
                t.singular_name_short,
                t.squad_select,
                t.squad_min_play,
                t.squad_max_play,
                t.element_count,
                t.load_date,
                t.run_id AS source_run_id
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY element_type_id ORDER BY load_date DESC) AS rn
                FROM bronze_element_types
            ) t
            WHERE t.rn = 1
            ON CONFLICT (element_type_id) DO UPDATE SET
                plural_name         = EXCLUDED.plural_name,
                singular_name       = EXCLUDED.singular_name,
                singular_name_short = EXCLUDED.singular_name_short,
                squad_select        = EXCLUDED.squad_select,
                squad_min_play      = EXCLUDED.squad_min_play,
                squad_max_play      = EXCLUDED.squad_max_play,
                element_count       = EXCLUDED.element_count,
                load_date           = EXCLUDED.load_date,
                source_run_id       = EXCLUDED.source_run_id
            """
        )
        rows_affected = cur.rowcount

    conn.commit()
    print(f"Transformed and upserted {rows_affected} element types into silver_element_types.")


if __name__ == "__main__":
    conn = get_connection()
    transform_element_types(conn)
    conn.close()