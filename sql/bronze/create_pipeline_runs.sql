-- pipeline_runs: tracks every ingestion attempt (per source, per run) - not 
-- just the final outcome. One row per attempt, never overwritten, so we can 
-- see every retry: which failed, why, and which one eventually succeeded. 
-- This is what powers monitoring/alerting and lets us audit pipeline reliability.
create table pipeline_runs(
run_id bigint generated always as identity primary key,
source_name text not null,
run_timestamp timestamp not null,
status text not null,
rows_loaded bigint not null,
error_message text
);