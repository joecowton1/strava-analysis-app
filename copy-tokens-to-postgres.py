#!/usr/bin/env python3
"""
Quick script to copy OAuth tokens from local SQLite to Cloud SQL PostgreSQL
"""

# Token data from local SQLite
athlete_id = 47642272
access_token = "3d9c5ba4d445cabf45305af160605e706fc4d347"
refresh_token = "20d110036d29de3dadba590e0952994de585f0a0"
expires_at = 1771014632

print("📋 Copy this SQL and run it in Cloud SQL:")
print()
print("In Cloud Shell, run:")
print("  gcloud sql connect strava-db --user=strava_app --database=strava")
print()
print("Password: o5g2FwxGc6RNkcr2nhuYuOPfZ")
print()
print("Then paste this SQL:")
print()
print(f"INSERT INTO tokens(athlete_id, access_token, refresh_token, expires_at)")
print(f"VALUES ({athlete_id}, '{access_token}', '{refresh_token}', {expires_at})")
print(f"ON CONFLICT(athlete_id) DO UPDATE SET")
print(f"  access_token=EXCLUDED.access_token,")
print(f"  refresh_token=EXCLUDED.refresh_token,")
print(f"  expires_at=EXCLUDED.expires_at;")
print()
print("One-liner version:")
print()
print(f"INSERT INTO tokens VALUES ({athlete_id}, '{access_token}', '{refresh_token}', {expires_at}) ON CONFLICT(athlete_id) DO UPDATE SET access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token, expires_at=EXCLUDED.expires_at;")

