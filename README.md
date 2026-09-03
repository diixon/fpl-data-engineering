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

## Project structure