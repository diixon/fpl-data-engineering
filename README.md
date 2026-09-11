# FPL Data Engineering Project

## About this project

This project is an end-to-end data pipeline for Fantasy Premier League 
(FPL) data. It pulls live data from the official FPL API, stores it, 
cleans it, validates it, and prepares it for a dashboard.

I built this as a portfolio project to show real Data Engineering skills: 
pipeline design, data quality checks, and a proper database structure - 
not just writing queries on top of existing data.

## Tech stack

- PostgreSQL - main database
- Python (psycopg v3) - ingestion, quality check, and transformation scripts
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
saved. `snapshot_type` is calculated dynamically for players, teams, and 
fixtures, based on real gameweek/deadline/match state, not hardcoded.

Shared logic (database connection, and a reusable ingestion function for 
JSON-based tables) lives in `src/db_utils.py`.

## Gate 1 - Bronze Data Quality Checks

Table constraints (NOT NULL, foreign keys) only protect the outer shape 
of a row - they can't see inside the raw JSON itself, so a malformed or 
incomplete API response could still insert without error. Gate 1 closes 
that gap by checking what's actually inside the JSON.

Results are recorded in a `quality_check_results` table - which table, 
which rule, how many rows were checked, how many failed, and the actual 
failed ids (not just a count, since a count alone isn't enough to act on).

Gate 1 covers:
- `bronze_players` - required fields exist inside raw_json, and status 
  codes are one of the 5 known values (an unexpected code is flagged here 
  rather than silently mapped to a default downstream)
- `bronze_fixtures` - required fields always present, and score fields 
  checked only on finished matches
- `bronze_teams` - required fields always present
- `bronze_event` - required stats exist inside the nested stats object

`bronze_element_types` needs no check - it uses real typed columns, not 
JSONB, so NOT NULL constraints already catch everything a check would.

The check logic (`run_quality_check`) is shared and reusable, in 
`src/quality_checks/quality_utils.py`.

## Silver transformation

Bronze data is cleaned, typed, and standardized into Silver tables:

- `transform_players.py` - converts price, translates status codes into 
  full words, picks the latest snapshot per player, excludes rows flagged 
  by Gate 1
- `transform_teams.py` - straight extraction and type casting
- `transform_fixtures.py` - only finished matches, filtered before ranking 
  snapshots (so a live snapshot can never outrank a finished one)
- `transform_element_types.py` - a simple flattened copy, deduplicated 
  since this table gets a new row inserted daily
- `transform_player_gameweek_stats.py` - the most complex one: joins two 
  Bronze sources (`bronze_event` for match stats, `bronze_players` for 
  transfer counts, since that field only exists in one of the two)

All Silver tables use `ON CONFLICT DO UPDATE`, making every script safe 
to re-run. Rows that failed a Gate 1 check are excluded here - not 
blocked entirely, not silently let through, just left out and logged, so 
good data isn't held back by a few bad rows.

## Gold population

Silver data is joined and denormalized into the final, dashboard-ready 
Gold layer:

- `populate_gold_teams.py` / `populate_gold_players.py` - players 
  denormalizes position and team name directly (a deliberate trade-off: 
  cheap here since this table is small, keeps dashboard queries simple)
- `populate_gold_fixture_results.py` - joins the teams table twice (once 
  for home, once for away) to get both team names
- `populate_gold_player_gameweek_performance.py` - kept normalized on 
  purpose, since this table grows every gameweek and denormalizing would 
  multiply storage cost for no real benefit
- `populate_gold_player_price_history.py` - the one Gold table with no 
  direct Silver source; it reads Bronze directly to detect real price 
  changes (`cost_change_event != 0`), and only creates a row when a 
  player's price actually moved that gameweek

## Gate 2 - Silver to Gold reconciliation

Gate 1 checks the raw source data. Gate 2 checks a narrower, more honest 
thing: whether my own transformation logic silently lost rows during a 
join. `check_gold_reconciliation.py` compares row counts between each 
Silver table and its Gold target - they should always match, since none 
of these transformations intentionally filter anything out.

This check does not catch every possible bug - a mistake that keeps the 
row count the same (like a home/away team swap) would not be caught here. 
It only catches the "rows disappeared" class of bug, which is a real and 
common failure mode for JOIN-based transformations.

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
- [x] Bronze ingestion for all three FPL API endpoints
- [x] Dynamic snapshot_type logic
- [x] Reusable, DRY ingestion functions shared across scripts
- [x] Gate 1 quality checks for all applicable Bronze tables
- [x] Silver transformation for all 5 tables
- [x] Gold population for all 5 tables
- [x] Gate 2 row-count reconciliation check
- [ ] Docker + Docker Compose
- [ ] Airflow orchestration
- [ ] Deployment on Azure
