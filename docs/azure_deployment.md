# Azure Deployment Guide

> **Status: documented, not deployed.** This guide is the plan I would follow. I have not run it on Azure yet, so treat the exact portal labels and prices as things to check, not as tested facts.

## Why Azure?

I chose Azure because it is a common platform in Data Engineering jobs, and because deploying the pipeline there shows the architecture is not tied to my laptop. Locally everything runs with Docker Compose; in the cloud I split it into two managed pieces:

1. **Azure Database for PostgreSQL (Flexible Server)** - holds my FPL data (Bronze, Silver, Gold). Backups and patching are handled by Azure.
2. **A Linux Virtual Machine** - runs the Docker containers (Airflow webserver and scheduler). I chose a VM over Azure Container Instances because Airflow needs persistent storage for logs and DAGs, which is simpler on a VM.

> **Cost warning:** both pieces are paid resources, not free ones. Before creating anything I check the Azure pricing calculator and whether my account has free credits or a student offer (offers change, so I read the current terms). I also stop the VM when I am not using it, and delete the whole resource group when the project is finished.

## 1. Database (Azure PostgreSQL Flexible Server)

1. In the Azure Portal, create an **Azure Database for PostgreSQL Flexible Server**.
2. Choose a server name (for example `fpl-postgres-server`), an admin username and a strong password. I save them safely - they replace the local credentials in `.env`.
3. Compute: the smallest **Burstable** size is enough for this data volume (~600 players, ~380 fixtures, one new snapshot per day).
4. Networking: **Public access**, with firewall rules for (a) my own IP, so DBeaver can connect, and (b) the VM's public IP, added after I create the VM in step 2. Azure requires SSL by default; the Python driver negotiates it automatically.
5. The server starts with only the default `postgres` database. I create my own database named `fpl_db` (DBeaver: right click, Create database).
6. I create the tables by running my SQL files **in this exact order** (the same order `sql/init-db.sh` uses locally). I do not run `init-db.sh` itself, because it also creates the Airflow metadata database, which stays on the VM:

   1. `sql/bronze/create_pipeline_runs.sql`
   2. `sql/bronze/create_bronze_tables.sql`
   3. `sql/silver/create_silver_tables.sql`
   4. `sql/silver/add_silver_constraints.sql`
   5. `sql/gold/create_gold_tables.sql`
   6. `sql/quality_checks/create_quality_check_results.sql`

## 2. Airflow (Azure Virtual Machine)

1. Create a **Linux VM**: Ubuntu Server 22.04 LTS, a size with **at least 4 GB RAM** (Airflow with LocalExecutor is slow or unstable below that), SSH key login.
2. Network security rules: allow SSH (22) **only from my IP**, and nothing else. I do **not** open port 8080: `docker-compose.yml` binds the Airflow UI to `127.0.0.1`, so it is reached through an SSH tunnel (step 7). An Airflow login open to the internet could run commands on the VM.
3. Add the VM's public IP to the PostgreSQL firewall rules (step 1.4).
4. Connect and install Docker (the official script installs Docker Engine and the `docker compose` plugin):

   ```bash
   ssh azureuser@<vm-public-ip>
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```

5. Clone the repository and create `.env`:

   ```bash
   git clone https://github.com/diixon/fpl-data-engineering.git
   cd fpl-data-engineering
   cp .env.example .env
   ```

   In `.env`, set `DB_USER`, `DB_PASSWORD` and `DB_NAME` to the Azure database values, and add:

   ```text
   DOCKER_DB_HOST=<server-name>.postgres.database.azure.com
   AIRFLOW_ADMIN_PASSWORD=<a strong password>
   AIRFLOW_FERNET_KEY=<generate with: openssl rand -base64 32 | tr '+/' '-_'>
   AIRFLOW_WEBSERVER_SECRET_KEY=<generate with: openssl rand -hex 32>
   AIRFLOW_UID=<output of: id -u>
   ```

   Also run `mkdir -p logs` before the first start (`logs/` is in `.gitignore`, so the clone does not have it).

   `DOCKER_DB_HOST` is the address the containers use for my FPL data (locally it defaults to the `postgres` container). The local Postgres container still starts on the VM, but it only holds Airflow's own metadata there.

6. Start everything:

   ```bash
   docker compose up -d --build
   ```

7. From my own computer, open an SSH tunnel: `ssh -L 8080:localhost:8080 azureuser@<vm-public-ip>`. While it is open, go to `http://localhost:8080` and log in with `admin` and the `AIRFLOW_ADMIN_PASSWORD` from `.env`. Then turn the `fpl_data_pipeline` DAG on and trigger it.

## 3. Check that it works

- In DBeaver (connected to the Azure server), `pipeline_runs` should show rows with `status = 'success'`, and `quality_check_results` should have rows from Gate 1 and Gate 2.
- The six queries in `sql/gold/dashboard_queries.sql` should return data once the DAG has finished.

## 4. Cleaning up

When I am done: stop (deallocate) the VM, or delete the whole resource group, so nothing keeps costing money.
