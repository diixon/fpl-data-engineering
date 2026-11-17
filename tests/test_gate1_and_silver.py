"""Gate 1 checks + the Silver transformations that depend on them."""
from datetime import datetime, timedelta

from src.quality_checks.check_bronze_players import check_bronze_players
from src.quality_checks.check_bronze_event import check_bronze_event
from src.transformation.transform_teams import transform_teams
from src.transformation.transform_element_types import transform_element_types
from src.transformation.transform_players import transform_players
from src.transformation.transform_player_gameweek_stats import transform_player_gameweek_stats
from tests.conftest import scalar


def prepare_lookups(db, seed):
    seed.team(); seed.element_type()
    transform_teams(db); transform_element_types(db)


def test_every_player_flagged_by_gate1_is_excluded_not_just_one(db, seed):
    prepare_lookups(db, seed)
    for i in range(1, 11):
        seed.player(i, status="x" if i <= 5 else "a")          # 5 invalid statuses
    check_bronze_players(db)
    transform_players(db)
    assert scalar(db, "select count(*) from silver_players") == 5
    assert scalar(db, "select min(player_id) from silver_players") == 6


def test_an_old_failed_check_does_not_exclude_players_after_a_passing_check(db, seed):
    prepare_lookups(db, seed)
    seed.player(1, status="x")
    check_bronze_players(db)                                    # flags player 1
    with db.cursor() as cur:
        cur.execute("update bronze_players set raw_json = jsonb_set(raw_json, '{status}', '\"a\"')")
    db.commit()
    check_bronze_players(db)                                    # newest check passes
    transform_players(db)
    assert scalar(db, "select count(*) from silver_players") == 1


def test_gate1_judges_only_the_newest_snapshot(db, seed):
    seed.player(1, load_date=datetime.now() - timedelta(days=5), drop_keys=("now_cost",))  # old, broken
    seed.player(1)                                                                          # new, fine
    check_bronze_players(db)
    failed = scalar(db, "select rows_failed from quality_check_results where rule_name = 'required_keys_missing'")
    assert failed == 0


def test_a_player_missing_from_silver_does_not_crash_the_gameweek_stats(db, seed):
    prepare_lookups(db, seed)
    seed.player(1); seed.player(2, status="x")                  # player 2 never reaches silver_players
    seed.event(1); seed.event(2)
    check_bronze_players(db); check_bronze_event(db)
    transform_players(db)
    transform_player_gameweek_stats(db)                          # used to raise ForeignKeyViolation
    assert scalar(db, "select count(*) from silver_player_gameweek_stats") == 1
    assert scalar(db, "select player_id from silver_player_gameweek_stats") == 1
