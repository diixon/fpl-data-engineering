# FPL Data Engineering Project

## About this project

This project is an end-to-end data pipeline for Fantasy Premier League 
(FPL) data. It pulls live data from the official FPL API, stores it, 
cleans it, and prepares it for a dashboard.

I built this as a portfolio project to show real Data Engineering skills: 
pipeline design, data quality checks, and a proper database structure - 
not just writing queries on top of existing data.

## Tech stack

- PostgreSQL - main database
- Python (psycopg v3) - ingestion and quality check scripts
- DBeaver - database client
- Docker + Airflow - orchestration (planned)
- Azure - deployment (planned)

## Architecture

I use a Medallion Architecture: Bronze, Silver, Gold.

- **Bronze**: raw data, exactly as it comes from the FPL API. Stored as 
  JSON, with no changes. This keeps a safe, unmodified copy in case 
  anything downstream needs to be reprocessed.
- **Silver**: cleaned and typed data. Fields are extracted from the raw 
  JSON, converted to the right types, and standardized (for example, 
  player price is converted from a raw integer into a real decimal value).
- **Gold**: final tables, ready for a dashboard. Some tables are 
  denormalized on purpose, so dashboard queries stay fast and simple.

A `pipeline_runs` table tracks every ingestion attempt, not just the final 
result. If something fails, I can see exactly when it failed and why, on 
the same day, instead of finding out later.

## Database design

16 tables in total (6 Bronze, 5 Silver, 5 Gold). Every table and column 
has a reason behind it, documented directly in the SQL files - why some 
tables are denormalized and others are not, why some tables carry 
traceability columns (`load_date`, `source_run_id`) and others don't.

The schema is built around 6 real questions a dashboard needs to answer:

1. Show all midfielders under £8.0m, sorted by total points
2. Find the best points-per-price value
3. Show how a player's price changed over time
4. Show the most transferred-in players this gameweek
5. Compare a player's actual points with their expected points (xG/xA)
6. Show which players are injured or doubtful right now

## Bronze ingestion

Three ingestion scripts pull data from the FPL API into Bronze:

- `ingest_bootstrap_static.py` - players, teams, and element types 
  (player positions), from the `bootstrap-static` endpoint
- `ingest_fixtures.py` - all fixtures, from the `fixtures` endpoint
- `ingest_event.py` - per-player gameweek stats, from `event/{gw}/live`, 
  but only once a gameweek is fully finished (this table has a unique 
  constraint per player per gameweek, so the same gameweek can't be 
  pulled twice)

Every script tracks its own run in `pipeline_runs`, with a try/except and 
rollback - if something fails partway through, nothing gets partially 
saved. The failure path is tested with a deliberate bug, to confirm the 
rollback and error logging actually work, not just assumed.

`snapshot_type` is calculated dynamically, not hardcoded. For players and 
teams, it checks the current gameweek's deadline/live/finished status once 
per run. For fixtures, each fixture is checked individually, since matches 
in the same gameweek can be in different states at the same time.

Shared logic (database connection, and a reusable ingestion function for 
JSON-based tables) lives in `src/db_utils.py`, so all scripts reuse the 
same tested code instead of repeating it.

## Gate 1 - Data Quality Checks

Before Bronze data can be trusted for Silver, it goes through quality 
checks. Table constraints (NOT NULL, foreign keys) only protect the outer 
shape of a row - they can't see inside the raw JSON itself, so a malformed 
or incomplete API response could still insert without error. Gate 1 closes 
that gap.

Results are recorded in a `quality_check_results` table - which table, 
which rule, how many rows were checked, how many failed, and the actual 
failed ids (not just a count, since a count alone isn't enough to act on). 
This table doesn't link to a single `pipeline_runs.run_id`, since a check 
usually looks at data from many different ingestion runs mixed together.

Gate 1 currently covers:
- `bronze_players` - required fields exist inside raw_json
- `bronze_fixtures` - required fields always present, plus a separate rule 
  for score fields, checked only on finished matches
- `bronze_teams` - required fields always present
- `bronze_event` - required stats exist inside the nested stats object

`bronze_element_types` doesn't need a check at all - that table uses real, 
typed columns instead of JSONB, so NOT NULL constraints already reject any 
row missing a required field before it's ever inserted. There's no hidden 
JSON blob where a problem could slip through, so there's nothing for Gate 1 
to catch that the table doesn't already enforce on its own.

The check logic (`run_quality_check`) is shared and reusable, in 
`src/quality_checks/quality_utils.py`.

When a check finds bad rows, Silver won't block entirely (that would also 
skip the good rows for no reason) and won't just log a warning and let bad 
data through either. Instead, Silver will exclude the specific rows listed 
in `failed_ids`, process everything else normally, and log what was 
skipped. This isn't wired in yet - it will be built alongside Silver 
transformation logic.

## Project structure

```text
sql/
├── bronze/                 # Bronze layer table definitions
├── silver/                 # Silver layer table definitions
├── gold/                   # Gold layer table definitions
└── quality_checks/         # quality_check_results table definition

src/
├── db_utils.py             # shared database connection and shared ingestion logic
├── ingestion/              # scripts that pull data from the FPL API into Bronze
├── quality_checks/         # Gate 1 data quality checks (Bronze layer)
└── transformation/         # Bronze to Silver to Gold logic (planned)

docs/
└── schema-design.md        # my Gold schema design notes
```

## Current progress

- [x] Full database design (Bronze, Silver, Gold - 16 tables)
- [x] Ingestion script for `bootstrap-static` (players, teams, element types)
- [x] Ingestion script for `fixtures`
- [x] Ingestion script for `event/{gw}/live` (gated on gameweek being finished)
- [x] Dynamic snapshot_type logic
- [x] Reusable, DRY ingestion functions shared across scripts
- [x] Gate 1 quality checks for all applicable Bronze tables
- [ ] Silver transformation logic
- [ ] Gate 2 quality checks
- [ ] Gold population logic
- [ ] Docker + Docker Compose
- [ ] Airflow orchestration
- [ ] Deployment on Azure
