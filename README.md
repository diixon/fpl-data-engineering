# FPL Data Engineering Project

## About this project

This is my portfolio project. I am a final-year Computer Science student, 
and I am moving from Data Analyst work into Data Engineering. I built this 
project to practice real Data Engineering skills, not just data analysis.

I use Fantasy Premier League (FPL) data. I chose this topic because I like 
football, and because the FPL API gives real, live data for free.

## What I want to learn

Before this project, I only knew SQL Server, Python, and pandas. In this 
project, I want to use new tools:

- PostgreSQL (instead of SQL Server)
- DBeaver (instead of SSMS)
- psycopg (version 3) to connect Python to Postgres
- Docker and Airflow (later stages)
- Azure (for deployment, later stage)

## Architecture

I use a Medallion Architecture: Bronze, Silver, Gold.

- **Bronze**: raw data, exactly as it comes from the FPL API. I store it as 
  JSON, with no changes. This way, I always have a safe copy if something 
  goes wrong later.
- **Silver**: cleaned and typed data. I remove fields I don't need, and I 
  fix data types (for example, I convert player price from a raw number 
  to a real decimal value).
- **Gold**: final tables, ready for a dashboard. Some tables here are 
  denormalized on purpose, to make dashboard queries fast and simple.

I also built a `pipeline_runs` table. This table tracks every ingestion 
attempt - not just the final result. If something fails, I can see exactly 
when it failed and why, on the same day, instead of finding out later.

## Database design

I designed 16 tables in total (6 Bronze, 5 Silver, 5 Gold). Every table 
and every column has a real reason behind it. I wrote comments in all my 
SQL files to explain my decisions - for example, why some tables are 
denormalized and others are not, and why some tables need traceability 
columns (`load_date`, `source_run_id`) and others don't.

I designed the tables around 6 real questions a dashboard should answer:

1. Show all midfielders under £8.0m, sorted by total points
2. Find the best points-per-price value
3. Show how a player's price changed over time
4. Show the most transferred-in players this gameweek
5. Compare a player's actual points with their expected points (xG/xA)
6. Show which players are injured or doubtful right now

## Bronze ingestion

I built three Python scripts that pull data from the FPL API into my 
Bronze tables:

- `ingest_bootstrap_static.py` - pulls players, teams, and element types 
  (player positions) from the `bootstrap-static` endpoint
- `ingest_fixtures.py` - pulls all fixtures from the `fixtures` endpoint
- `ingest_event.py` - pulls per-player gameweek stats from the 
  `event/{gw}/live` endpoint, but only once a gameweek is fully finished 
  (this table has a unique constraint per player per gameweek, so I can't 
  pull the same gameweek twice)

Every script tracks its own run in `pipeline_runs`, and uses a try/except 
with rollback - if something fails partway through, nothing gets partially 
saved. I tested this failure path on purpose, with a deliberate bug, to 
make sure it actually works, not just assumed it works.

I also calculate `snapshot_type` dynamically now, instead of hardcoding it. 
For players and teams, I check the current gameweek's deadline/live/finished 
status once per run. For fixtures, I check each fixture's own `started`/
`finished` fields, since every fixture can be in a different state at the 
same time.

Shared logic (the database connection, and the reusable ingestion function 
for JSON-based tables) lives in `src/db_utils.py`, so all three scripts 
reuse the same tested code instead of repeating it.

## Project structure

```text
sql/
├── bronze/                 # Bronze layer table definitions
├── silver/                 # Silver layer table definitions
└── gold/                   # Gold layer table definitions

src/
├── db_utils.py             # Shared database connection and shared ingestion logic
├── ingestion/              # Scripts that pull data from the FPL API into Bronze
├── quality_checks/         # Data quality checks (planned)
└── transformation/         # Bronze to Silver to Gold logic (planned)

docs/
└── schema-design.md        # My Gold schema design notes
```

## Current progress

- [x] Full database design (Bronze, Silver, Gold - 16 tables)
- [x] Ingestion script for `bootstrap-static` (players, teams, element types)
- [x] Ingestion script for `fixtures`
- [x] Ingestion script for `event/{gw}/live` (gated on gameweek being finished)
- [x] Dynamic snapshot_type logic (no more hardcoded values)
- [x] Reusable, DRY ingestion functions shared across scripts
- [ ] Data quality checks (Gate 1, Gate 2)
- [ ] Silver transformation logic
- [ ] Gold population logic
- [ ] Docker + Docker Compose
- [ ] Airflow orchestration
- [ ] Deployment on Azure

## How I built this

I did not write code first. I planned the whole architecture on paper 
before writing any SQL or Python - the data flow, the reliability design 
(retries, monitoring), the database schema, all of it. I only started 
coding once I understood *why* each piece existed, not just *how* to 
build it.

I also debugged real bugs along the way instead of avoiding them - a 
tuple-unpacking bug that silently gave wrong results, a Python import 
that accidentally re-ran an entire script as a side effect, and a schema 
gap I found by checking my tables against my own 6 dashboard 
questions. Each one taught me something I would not have learned by 
just copying working code.
