# FPL Data Engineering Project

## About this project

This project is an end-to-end data pipeline for Fantasy Premier League (FPL) data. It pulls live data from the official FPL API, stores it, cleans it, validates it, and prepares it for a dashboard.

I built this as a portfolio project to demonstrate real Data Engineering skills: pipeline design, data quality checks, orchestration, containerization, and proper database structuring—not just writing queries on top of existing data.

## Tech Stack

- **PostgreSQL** - Main database (Bronze, Silver, Gold layers)
- **Python (psycopg v3)** - Ingestion, quality check, and transformation scripts
- **Apache Airflow** - Orchestration and scheduling
- **Docker & Docker Compose** - Containerization and local environment setup
- **Azure** - Cloud deployment (Documented)
- **DBeaver** - Database client

## Architecture

I use a Medallion Architecture: Bronze, Silver, Gold.

- **Bronze**: Raw data, exactly as it comes from the FPL API. Stored as JSONB, with no changes. This keeps a safe, unmodified copy in case anything downstream needs to be reprocessed.
- **Silver**: Cleaned and typed data. Fields are extracted from the raw JSON, converted to the right types, and standardized (for example, player price is converted from a raw integer into a real decimal value).
- **Gold**: Final tables, ready for a dashboard. Some tables are denormalized on purpose, so dashboard queries stay fast and simple.

A `pipeline_runs` table tracks every ingestion attempt, not just the final result. If something fails, I can see exactly when it failed and why, on the same day, instead of finding out later.

## Database Design

16 tables in total (6 Bronze, 5 Silver, 5 Gold). Every table and column has a reason behind it, documented directly in the SQL files—why some tables are denormalized and others are not, why some tables carry traceability columns (`load_date`, `source_run_id`) and others don't.

The schema is built around 6 real questions a dashboard needs to answer:

1. Show all midfielders under £8.0m, sorted by total points
2. Find the best points-per-price value
3. Show how a player's price changed over time
4. Show the most transferred-in players this gameweek
5. Compare a player's actual points with their expected points (xG/xA)
6. Show which players are injured or doubtful right now

## Orchestration & Containerization

I use **Apache Airflow** to orchestrate the pipeline and **Docker Compose** to run the entire stack locally.

- `Dockerfile`: I use the Python 3.11 version of the official Airflow image. I switched to 3.11 because the `psycopg` v3 library requires Python 3.9 or newer. Running `pip install` as the `airflow` user ensures packages are installed in the correct local site-packages directory.
- `docker-compose.yml`: I use YAML anchors (`x-airflow-common`) to define the base configuration once, preventing repetition across the webserver, scheduler, and init containers.
- `fpl_pipeline_dag.py`: The DAG enforces strict execution order. For example, `transform_teams` must finish before `transform_players` and `transform_fixtures` because of Foreign Key constraints in Silver.
- **Database Initialization**: The `init-db.sh` script automatically creates the Airflow metadata database and executes all my Bronze, Silver, and Gold SQL files in the exact dependency order on the first startup.

## Cloud Deployment (Azure)

While the pipeline runs locally via Docker Compose, I also documented the deployment strategy for Microsoft Azure to prove the architecture is production-ready.

See the full step-by-step guide in [`docs/azure_deployment.md`](https://chat.deepseek.com/a/chat/s/docs/azure_deployment.md).

## Project Structure

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
└── transformation/         # Bronze to Silver to Gold logic

dags/
└── fpl_pipeline_dag.py     # Airflow DAG orchestrating the entire pipeline

docs/
├── schema-design.md        # my Gold schema design notes
└── azure_deployment.md     # Cloud deployment guide

Dockerfile                  # Custom Airflow image with dependencies
docker-compose.yml          # Local multi-container orchestration
```

## How to Run Locally

### Prerequisites

Docker Desktop installed and running.

### Steps

1. Clone the repository.

2. Create your environment file:

```bash
cp .env.example .env
```

3. Start the containers:

```bash
docker-compose up -d --build
```

4. Wait for Airflow to initialize. Then, access the Airflow UI at http://localhost:8080 (Username: admin, Password: admin).

5. Trigger the `fpl_data_pipeline` DAG to run the entire pipeline.

## Current Progress

- ☑ Full database design (Bronze, Silver, Gold - 16 tables)
- ☑ Bronze ingestion for all three FPL API endpoints
- ☑ Dynamic snapshot_type logic
- ☑ Reusable, DRY ingestion functions shared across scripts
- ☑ Gate 1 quality checks for all applicable Bronze tables
- ☑ Silver transformation for all 5 tables
- ☑ Gold population for all 5 tables
- ☑ Gate 2 row-count reconciliation check
- ☑ Docker + Docker Compose
- ☑ Airflow orchestration
- ☑ Azure deployment documentation