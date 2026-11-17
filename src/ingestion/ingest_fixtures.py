import sys
from src.db_utils import (
    get_connection, fetch_json, ingest_jsonb_entity, determine_fixture_snapshot_type,
)

FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"


def main():
    data = fetch_json(FIXTURES_URL)
    print(f"Fetched {len(data)} fixtures from the API.")

    # Unlike players/teams, I pass the function directly here, no lambda -
    # each fixture is different (some finished, some not), so this function
    # needs to run fresh for every single fixture, using that fixture's own
    # started/finished fields.
    with get_connection() as conn:
        ok = ingest_jsonb_entity(conn, "fixtures", "fixture", data,
                                 "fixtures", determine_fixture_snapshot_type)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
