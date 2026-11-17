from src.quality_checks.check_bronze_players import check_bronze_players
from src.quality_checks.check_gold_reconciliation import check_gold_reconciliation
from src.transformation.transform_teams import transform_teams
from src.transformation.transform_element_types import transform_element_types
from src.transformation.transform_players import transform_players
from src.transformation.populate_gold_teams import populate_gold_teams
from src.transformation.populate_gold_players import populate_gold_players
from src.transformation.populate_gold_player_price_history import populate_gold_player_price_history
from tests.conftest import scalar


def build_silver_and_gold(db, seed):
    seed.team(); seed.element_type()
    seed.player(1, cost_change=1); seed.player(2, status="x", cost_change=1); seed.player(3)
    check_bronze_players(db)
    transform_teams(db); transform_element_types(db); transform_players(db)
    populate_gold_teams(db); populate_gold_players(db)


def test_price_history_skips_players_that_are_not_in_gold_players(db, seed):
    build_silver_and_gold(db, seed)
    populate_gold_player_price_history(db, gameweek=12)         # player 2 has a change but is not in Gold
    assert scalar(db, "select count(*) from player_price_history") == 1
    assert scalar(db, "select player_id from player_price_history") == 1


def test_gate2_returns_no_mismatch_when_silver_and_gold_match(db, seed):
    build_silver_and_gold(db, seed)
    assert check_gold_reconciliation(db) == []


def test_gate2_reports_the_table_that_lost_rows(db, seed):
    build_silver_and_gold(db, seed)
    with db.cursor() as cur:
        cur.execute("delete from players where player_id = 3")
    db.commit()
    assert check_gold_reconciliation(db) == ["players"]
    assert scalar(db, "select rows_failed from quality_check_results "
                      "where table_name = 'players' and rule_name = 'silver_gold_row_count_mismatch'") == 1
