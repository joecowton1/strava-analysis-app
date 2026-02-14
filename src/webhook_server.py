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
)

s = get_settings()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
        con.execute(
            "INSERT INTO webhook_events(received_at, object_id, owner_id, aspect_type, object_type, subscription_id, updates_json) VALUES (?,?,?,?,?,?,?)",
            (int(time.time()), evt.object_id, evt.owner_id, evt.aspect_type, evt.object_type, evt.subscription_id, updates_json),
        )
        con.commit()
        log.info("Webhook event queued (object_id=%s)", evt.object_id)
        return {"ok": True}
    except Exception:
        log.exception("Failed to enqueue webhook event (object_id=%s)", evt.object_id)
        raise
    finally:
        con.close()

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
        con.close()


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
        con.close()
