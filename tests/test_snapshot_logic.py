"""Pure logic tests - no database needed."""
from datetime import datetime, timedelta, timezone

import pytest

from src.db_utils import determine_snapshot_type, determine_fixture_snapshot_type


def event(event_id, days_from_now, finished):
    when = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return {"id": event_id, "deadline_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "finished": finished}


def test_finished_gameweek_is_post_gameweek_and_returns_its_number():
    assert determine_snapshot_type([event(1, -3, True), event(2, 4, False)]) == ("post_gameweek", 1)


def test_started_but_unfinished_gameweek_is_live():
    assert determine_snapshot_type([event(1, -1, False)]) == ("live", None)


def test_before_the_season_raises_a_clear_error_instead_of_returning_none():
    with pytest.raises(ValueError, match="no gameweek deadline has passed"):
        determine_snapshot_type([event(1, 30, False)])


@pytest.mark.parametrize("started, finished, expected", [
    (False, False, "pre_match"),
    (True, False, "live"),
    (True, True, "post_match"),
])
def test_fixture_snapshot_type(started, finished, expected):
    assert determine_fixture_snapshot_type({"started": started, "finished": finished}) == expected
