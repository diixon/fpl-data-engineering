from src.db_utils import ingest_jsonb_entity
from src.ingestion.ingest_event import ingest_event, gameweek_already_ingested
from tests.conftest import scalar

import pytest


def test_successful_ingest_saves_rows_and_marks_the_run_success(db):
    items = [{"id": i, "name": f"T{i}"} for i in range(1, 21)]
    assert ingest_jsonb_entity(db, "teams", "team", items, "t_ok", lambda item: "live") is True
    assert scalar(db, "select count(*) from bronze_teams") == 20
    assert scalar(db, "select status from pipeline_runs where source_name = 't_ok'") == "success"
    assert scalar(db, "select rows_loaded from pipeline_runs where source_name = 't_ok'") == 20


def test_failed_ingest_rolls_back_everything_and_records_the_error(db):
    items = [{"id": 1}, {"id": 2}, {"name": "no id"}]          # third item breaks
    assert ingest_jsonb_entity(db, "teams", "team", items, "t_bad", lambda item: "live") is False
    assert scalar(db, "select count(*) from bronze_teams") == 0   # no half-saved rows
    assert scalar(db, "select status from pipeline_runs where source_name = 't_bad'") == "failed"
    assert scalar(db, "select error_message from pipeline_runs where source_name = 't_bad'")


def test_raise_on_error_re_raises_so_airflow_can_fail_the_task(db):
    with pytest.raises(KeyError):
        ingest_jsonb_entity(db, "teams", "team", [{"name": "no id"}], "t_raise",
                            lambda item: "live", raise_on_error=True)
    assert scalar(db, "select status from pipeline_runs where source_name = 't_raise'") == "failed"


def test_event_gameweek_is_not_ingested_twice(db):
    data = [{"id": 9, "stats": {}}]
    assert gameweek_already_ingested(db, 2) is False
    assert ingest_event(db, 2, data) is True
    assert gameweek_already_ingested(db, 2) is True
