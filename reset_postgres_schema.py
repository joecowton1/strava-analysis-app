#!/usr/bin/env python3
"""
Script to reset PostgreSQL schema with correct BIGINT types for large IDs.
Run this once after deploying the updated schema to Cloud Run.
"""
import os
os.environ["USE_POSTGRES"] = "true"
os.environ["DATABASE_URL"] = "postgresql://strava_app:o5g2FwxGc6RNkcr2nhuYuOPfZ@/strava?host=/cloudsql/strava-analysis-483921:europe-west2:strava-db"

from src.db import connect, USE_POSTGRES
import psycopg2

print(f"USE_POSTGRES: {USE_POSTGRES}")
print("Connecting to PostgreSQL...")

con = connect(None)
cursor = con.cursor()

print("Dropping existing tables...")
tables = ['progress_summaries', 'ride_analysis', 'activity_streams', 'activities', 'webhook_events', 'tokens']
for table in tables:
    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print(f"  ✓ Dropped {table}")
    except Exception as e:
        print(f"  ✗ Error dropping {table}: {e}")

con.commit()

print("\nRecreating tables with correct schema...")
from src.db import init_db
init_db(con)

print("\n✅ Schema reset complete!")
print("\nYou can now trigger a webhook and it should work.")

con.close()
