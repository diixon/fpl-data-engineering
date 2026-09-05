import requests
from src.db_utils import get_connection, ingest_jsonb_entity, determine_fixture_snapshot_type

if __name__ == "__main__":
    response = requests.get("https://fantasy.premierleague.com/api/fixtures/")
    data = response.json()
    print(f"Fetched {len(data)} fixtures from the API.")

    conn = get_connection()

    # Unlike players/teams, I pass the function directly here, no lambda -
    # each fixture is different (some finished, some not), so this function
    # needs to run fresh for every single fixture, using that fixture's own
    # started/finished fields.
    ingest_jsonb_entity(conn, "fixtures", "fixture", data,
                         "fixtures", determine_fixture_snapshot_type)
    conn.close()