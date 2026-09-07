-- quality_check_results: records every Gate 1 (and later Gate 2) check I
-- run - not just success/failure like pipeline_runs, but a measurement of
-- how much of the data in a table is actually broken, at the moment the
-- check runs.
--
-- I store failed_ids as a real JSONB list, not just a count, because a
-- count alone isn't useful - if I ever want to go fix or investigate
-- specific broken rows, I need the actual ids, not just "5 rows failed".
--
-- No run_id / foreign key to pipeline_runs on purpose: a check usually
-- looks at the whole table, which holds data from many different
-- ingestion runs mixed together - pointing to one single run_id would be
-- misleading. checked_at (a real timestamp) is enough to know when the
-- check happened.
CREATE TABLE quality_check_results (
    check_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name     TEXT NOT NULL,
    rule_name      TEXT NOT NULL,
    checked_at     TIMESTAMPTZ NOT NULL,
    rows_checked   BIGINT NOT NULL CHECK (rows_checked >= 0),
    rows_failed    BIGINT NOT NULL CHECK (rows_failed >= 0),
    failed_ids     JSONB,

    CONSTRAINT chk_rows_failed_le_checked CHECK (rows_failed <= rows_checked)
);
