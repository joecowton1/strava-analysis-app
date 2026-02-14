#!/usr/bin/env python3
"""
Script to programmatically refresh OAuth tokens for Strava athletes.

Usage:
    python -m src.refresh_tokens [athlete_id]

If no athlete_id is provided, refreshes tokens for all athletes in the database.
"""
from __future__ import annotations

import argparse
import sys

from .config import get_settings
from .db import connect, get_tokens, upsert_tokens
from .strava_client import StravaClient


def refresh_tokens_for_athlete(con, client: StravaClient, athlete_id: int) -> bool:
    """Refresh tokens for a specific athlete."""
    tokens = get_tokens(con, athlete_id)
    if not tokens:
        print(f"❌ No tokens found for athlete_id={athlete_id}")
        return False

    try:
        new_tokens = client.refresh_access_token(tokens["refresh_token"])
        upsert_tokens(
            con,
            athlete_id,
            new_tokens["access_token"],
            new_tokens["refresh_token"],
            new_tokens["expires_at"],
        )
        print(f"✅ Tokens refreshed for athlete_id={athlete_id}")
        return True
    except Exception as e:
        print(f"❌ Failed to refresh tokens for athlete_id={athlete_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Refresh OAuth tokens for Strava athletes"
    )
    parser.add_argument(
        "athlete_id",
        nargs="?",
        type=int,
        help="Athlete ID to refresh tokens for (if not provided, refreshes all athletes)",
    )
    args = parser.parse_args()

    s = get_settings()
    con = connect(s.db_path)
    client = StravaClient(s.client_id, s.client_secret)

    if args.athlete_id:
        # Refresh tokens for specific athlete
        success = refresh_tokens_for_athlete(con, client, args.athlete_id)
        sys.exit(0 if success else 1)
    else:
        # Refresh tokens for all athletes
        rows = con.execute("SELECT athlete_id FROM tokens").fetchall()
        if not rows:
            print("❌ No athletes found in database")
            sys.exit(1)

        print(f"Refreshing tokens for {len(rows)} athlete(s)...")
        success_count = 0
        for row in rows:
            athlete_id = row["athlete_id"]
            if refresh_tokens_for_athlete(con, client, athlete_id):
                success_count += 1

        print(f"\n✅ Successfully refreshed tokens for {success_count}/{len(rows)} athlete(s)")
        sys.exit(0 if success_count == len(rows) else 1)


if __name__ == "__main__":
    main()

