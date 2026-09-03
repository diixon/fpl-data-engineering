"""
db_utils.py — shared database connection logic.

Kept separate from any single ingestion/quality_checks/transformation script,
since every part of the pipeline needs to connect to Postgres. Written once
here, imported everywhere else, instead of repeating the same connection
setup in every script.
"""

import os
import psycopg
from dotenv import load_dotenv

def get_connection():
    load_dotenv()
    conn = psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    )
    print(f"Connected successfully!")
    return conn