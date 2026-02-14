import time
import json
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .config import get_settings
from .db import (
    connect,
    init_db,
    get_ride_analysis,
    list_ride_analyses_chronological,
    get_progress_summary,
    list_progress_summaries_chronological,
    USE_POSTGRES,
    close_connection,
)

s = get_settings()

# Database placeholder helper - PostgreSQL uses %s, SQLite uses ?
def _sql(query: str) -> str:
    """Convert SQLite-style ? placeholders to %s for PostgreSQL."""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

# Helper to execute queries (PostgreSQL needs cursor, SQLite doesn't)
def _execute(con, query: str, params=None):
    """Execute a query with proper handling for both SQLite and PostgreSQL."""
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        return cursor
    else:
        return con.execute(query, params)

# Basic logging setup (plays nicely with uvicorn; avoids logging secrets)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("strava.webhook_server")
log.info("Webhook server starting (db_path=%s)", str(Path(s.db_path).resolve()))

# Initialize database (only needed once at startup)
init_db(connect(s.db_path))

app = FastAPI()

# CORS for local frontend dev (Vite defaults to :5173) and production
import os
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Add production frontend URL from environment variable
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

# Allow all Cloud Run frontend URLs (*.run.app domains)
# This is safe since Cloud Run domains are GCP-controlled
import re
allow_origin_regex = r"https://.*\.run\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Event(BaseModel):
    aspect_type: str
    event_time: int
    object_id: int
    object_type: str
    owner_id: int
    subscription_id: int
    updates: dict = {}

# legacy simple verification removed — use the async verify(request: Request) handler below

@app.post("/strava/webhook")
def receive(evt: Event):
    log.info(
        "Webhook event received (subscription_id=%s owner_id=%s object_type=%s object_id=%s aspect_type=%s)",
        evt.subscription_id,
        evt.owner_id,
        evt.object_type,
        evt.object_id,
        evt.aspect_type,
    )
    # Create a new connection for this request (required for thread safety)
    con = connect(s.db_path)
    try:
        # Store updates as JSON (not Python repr)
        updates_json = json.dumps(evt.updates or {})
        _execute(con,
            _sql("INSERT INTO webhook_events(received_at, object_id, owner_id, aspect_type, object_type, subscription_id, updates_json) VALUES (?,?,?,?,?,?,?)"),
            (int(time.time()), evt.object_id, evt.owner_id, evt.aspect_type, evt.object_type, evt.subscription_id, updates_json),
        )
        con.commit()
        log.info("Webhook event queued (object_id=%s)", evt.object_id)
        return {"ok": True}
    except Exception:
        log.exception("Failed to enqueue webhook event (object_id=%s)", evt.object_id)
        raise
    finally:
        close_connection(con)

@app.get("/strava/webhook")
async def verify(request: Request):
    received = (request.query_params.get("hub.verify_token") or "").strip()
    challenge = request.query_params.get("hub.challenge")
    expected = (s.verify_token or "").strip()

    log.info(
        "Webhook verify request received (remote=%s verify_token_present=%s)",
        request.client.host if request.client else None,
        bool(received),
    )

    if received != expected:
        log.warning(
            "Webhook verify failed (remote=%s received=%s)",
            request.client.host if request.client else None,
            received,
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    log.info("Webhook verify succeeded")
    return {"hub.challenge": challenge}


@app.post("/api/backfill")
def backfill_activities():
    """
    Fetch historical activities from Strava and queue ride activities for processing.
    Also resets any stuck 'processing' events back to 'queued'.
    """
    from .strava_client import StravaClient
    from .config import get_settings

    settings = get_settings()
    client = StravaClient(settings.client_id, settings.client_secret)

    con = connect(s.db_path)
    try:
        # 1. Reset stuck 'processing' events to 'queued'
        _execute(con, _sql("UPDATE webhook_events SET status='queued' WHERE status='processing'"))
        con.commit()

        # 2. Get the first athlete's OAuth token
        cursor = _execute(con, "SELECT * FROM tokens LIMIT 1")
        tok = cursor.fetchone()
        if not tok:
            raise HTTPException(status_code=400, detail="No OAuth tokens found. Authenticate first.")

        athlete_id = tok["athlete_id"]
        access_token = tok["access_token"]
        refresh_token = tok["refresh_token"]
        expires_at = tok["expires_at"]

        # Refresh token if expired
        now_ts = int(time.time())
        if expires_at <= now_ts + 60:
            new_tokens = client.refresh_access_token(refresh_token)
            access_token = new_tokens["access_token"]
            # Update stored tokens
            if USE_POSTGRES:
                _execute(con,
                    """INSERT INTO tokens(athlete_id, access_token, refresh_token, expires_at)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT(athlete_id) DO UPDATE SET
                         access_token=EXCLUDED.access_token,
                         refresh_token=EXCLUDED.refresh_token,
                         expires_at=EXCLUDED.expires_at""",
                    (athlete_id, new_tokens["access_token"], new_tokens["refresh_token"], new_tokens["expires_at"]),
                )
            else:
                _execute(con,
                    "INSERT OR REPLACE INTO tokens(athlete_id, access_token, refresh_token, expires_at) VALUES (?,?,?,?)",
                    (athlete_id, new_tokens["access_token"], new_tokens["refresh_token"], new_tokens["expires_at"]),
                )
            con.commit()

        # 3. Fetch historical activities from Strava
        activities = client.list_athlete_activities(access_token, per_page=100, max_pages=20)

        # 4. Get existing activity IDs already queued/done
        cursor = _execute(con, "SELECT DISTINCT object_id FROM webhook_events")
        existing_ids = {row["object_id"] for row in cursor.fetchall()}

        # 5. Queue new ride activities
        ride_types = {"Ride", "VirtualRide", "EBikeRide"}
        queued_count = 0
        skipped_count = 0
        now = int(time.time())

        for act in activities:
            activity_id = act.get("id")
            sport_type = act.get("sport_type") or act.get("type")

            if sport_type not in ride_types:
                skipped_count += 1
                continue

            if activity_id in existing_ids:
                skipped_count += 1
                continue

            _execute(con,
                _sql("INSERT INTO webhook_events(received_at, object_id, owner_id, aspect_type, object_type, subscription_id, updates_json) VALUES (?,?,?,?,?,?,?)"),
                (now, activity_id, athlete_id, "create", "activity", 0, "{}"),
            )
            queued_count += 1

        con.commit()
        log.info("Backfill complete: queued=%d skipped=%d total_fetched=%d", queued_count, skipped_count, len(activities))
        return {
            "ok": True,
            "total_fetched": len(activities),
            "queued": queued_count,
            "skipped": skipped_count,
        }
    finally:
        close_connection(con)


@app.get("/api/reports")
def list_reports():
    """
    List available reports (ride analyses + progress summaries) newest-first.
    """
    con = connect(s.db_path)
    try:
        rides = list_ride_analyses_chronological(con)
        progress = list_progress_summaries_chronological(con)

        items = []
        for r in rides:
            act = r.get("activity") or {}
            items.append(
                {
                    "kind": "ride",
                    "activity_id": r["activity_id"],
                    "created_at": r["created_at"],
                    "model": r.get("model"),
                    "prompt_version": r.get("prompt_version"),
                    "name": act.get("name"),
                    "start_date": act.get("start_date"),
                    "sport_type": act.get("sport_type"),
                }
            )
        for p in progress:
            # Progress summaries should have a stable, date-based title (not the last ride name).
            created_at = int(p.get("created_at") or 0)
            date_str = time.strftime("%d/%m/%Y", time.localtime(created_at)) if created_at else ""
            title = f"Progress - {date_str}".strip()
            items.append(
                {
                    "kind": "progress",
                    "activity_id": p["activity_id"],
                    "created_at": p["created_at"],
                    "model": p.get("model"),
                    "prompt_version": p.get("prompt_version"),
                    "name": title or "Progress",
                    "start_date": None,
                    "sport_type": None,
                }
            )

        items.sort(key=lambda x: x["created_at"] or 0, reverse=True)
        return {"items": items}
    finally:
        close_connection(con)


@app.get("/api/reports/{kind}/{activity_id}")
def get_report(kind: str, activity_id: int):
    """
    Fetch a single report's markdown.
    kind: 'ride' or 'progress'
    """
    con = connect(s.db_path)
    try:
        if kind == "ride":
            r = get_ride_analysis(con, activity_id)
            if not r:
                raise HTTPException(status_code=404, detail="Ride report not found")
            return {
                "kind": "ride",
                "activity_id": r["activity_id"],
                "created_at": r["created_at"],
                "model": r.get("model"),
                "prompt_version": r.get("prompt_version"),
                "markdown": r.get("narrative") or "",
            }
        if kind == "progress":
            p = get_progress_summary(con, activity_id)
            if not p:
                raise HTTPException(status_code=404, detail="Progress report not found")
            return {
                "kind": "progress",
                "activity_id": p["activity_id"],
                "created_at": p["created_at"],
                "model": p.get("model"),
                "prompt_version": p.get("prompt_version"),
                "markdown": p.get("summary") or "",
            }
        raise HTTPException(status_code=400, detail="Invalid kind (expected 'ride' or 'progress')")
    finally:
        close_connection(con)
