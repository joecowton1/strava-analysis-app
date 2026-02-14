import time
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlencode

import jwt
import requests as http_requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from .config import get_settings
from .db import (
    connect,
    init_db,
    get_ride_analysis,
    list_ride_analyses_chronological,
    get_progress_summary,
    list_progress_summaries_chronological,
    upsert_tokens,
    get_tokens,
    is_athlete_allowed,
    USE_POSTGRES,
    close_connection,
)

s = get_settings()

# ── JWT Configuration ──────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 30 * 24 * 60 * 60  # 30 days
AUTH_COOKIE_NAME = "strava_session"

STRAVA_OAUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

# Where to redirect after successful OAuth (frontend URL)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Database placeholder helper - PostgreSQL uses %s, SQLite uses ?
def _sql(query: str) -> str:
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

# Helper to execute queries (PostgreSQL needs cursor, SQLite doesn't)
def _execute(con, query: str, params=None):
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        return cursor
    else:
        return con.execute(query, params)

# Basic logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("strava.webhook_server")
log.info("Webhook server starting (db_path=%s)", str(Path(s.db_path).resolve()))

# Initialize database
init_db(connect(s.db_path))

app = FastAPI()

# CORS
allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if FRONTEND_URL and FRONTEND_URL not in allowed_origins:
    allowed_origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.run\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── JWT helpers ────────────────────────────────────────────────────────────────

def _create_jwt(athlete_id: int, name: str | None = None) -> str:
    return jwt.encode(
        {"athlete_id": athlete_id, "name": name, "exp": int(time.time()) + JWT_EXPIRY_SECONDS, "iat": int(time.time())},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )

def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def get_current_athlete(request: Request) -> int:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_jwt(token)
    if not payload or "athlete_id" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return int(payload["athlete_id"])

def _set_auth_cookie(response, token: str):
    response.set_cookie(
        key=AUTH_COOKIE_NAME, value=token, httponly=True, secure=True,
        samesite="none", max_age=JWT_EXPIRY_SECONDS, path="/",
    )

def _get_callback_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https" and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return base + "/auth/callback"


# ── Auth endpoints ─────────────────────────────────────────────────────────────

@app.get("/auth/strava")
def auth_strava(request: Request):
    callback_url = _get_callback_url(request)
    params = {
        "client_id": s.client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "activity:read_all",
    }
    return RedirectResponse(f"{STRAVA_OAUTH_URL}?{urlencode(params)}")


@app.get("/auth/callback")
def auth_callback(request: Request, code: str = "", error: str | None = None):
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}?auth_error=denied")

    callback_url = _get_callback_url(request)

    try:
        r = http_requests.post(STRAVA_TOKEN_URL, data={
            "client_id": s.client_id, "client_secret": s.client_secret,
            "code": code, "grant_type": "authorization_code",
        }, timeout=30)
        r.raise_for_status()
        tok = r.json()
    except Exception:
        log.exception("Failed to exchange OAuth code")
        return RedirectResponse(f"{FRONTEND_URL}?auth_error=exchange_failed")

    athlete_id = tok["athlete"]["id"]
    athlete_name = f"{tok['athlete'].get('firstname', '')} {tok['athlete'].get('lastname', '')}".strip() or None

    con = connect(s.db_path)
    try:
        if not is_athlete_allowed(con, athlete_id):
            log.warning("Athlete %s (%s) not in allowed list", athlete_id, athlete_name)
            return RedirectResponse(f"{FRONTEND_URL}?auth_error=not_allowed")
        upsert_tokens(con, athlete_id, tok["access_token"], tok["refresh_token"], tok["expires_at"])
        log.info("OAuth complete for athlete %s (%s)", athlete_id, athlete_name)
    finally:
        close_connection(con)

    token = _create_jwt(athlete_id, athlete_name)
    response = RedirectResponse(FRONTEND_URL)
    _set_auth_cookie(response, token)
    return response


@app.get("/auth/me")
def auth_me(request: Request):
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_jwt(token)
    if not payload or "athlete_id" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {"athlete_id": payload["athlete_id"], "name": payload.get("name")}


@app.post("/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response


# ── Strava webhook endpoints (no auth - called by Strava) ─────────────────────

class Event(BaseModel):
    aspect_type: str
    event_time: int
    object_id: int
    object_type: str
    owner_id: int
    subscription_id: int
    updates: dict = {}

@app.post("/strava/webhook")
def receive(evt: Event):
    log.info("Webhook event received (owner_id=%s object_id=%s aspect_type=%s)", evt.owner_id, evt.object_id, evt.aspect_type)
    con = connect(s.db_path)
    try:
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
    if received != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"hub.challenge": challenge}


# ── Authenticated API endpoints ────────────────────────────────────────────────

@app.post("/api/backfill")
def backfill_activities(request: Request):
    athlete_id = get_current_athlete(request)

    from .strava_client import StravaClient
    client = StravaClient(s.client_id, s.client_secret)

    con = connect(s.db_path)
    try:
        _execute(con, _sql("UPDATE webhook_events SET status='queued' WHERE status='processing' AND owner_id=?"), (athlete_id,))
        con.commit()

        tok = get_tokens(con, athlete_id)
        if not tok:
            raise HTTPException(status_code=400, detail="No OAuth tokens found for this athlete.")

        access_token = tok["access_token"]
        if tok["expires_at"] <= int(time.time()) + 60:
            new_tokens = client.refresh_access_token(tok["refresh_token"])
            access_token = new_tokens["access_token"]
            upsert_tokens(con, athlete_id, new_tokens["access_token"], new_tokens["refresh_token"], new_tokens["expires_at"])

        activities = client.list_athlete_activities(access_token, per_page=100, max_pages=20)

        cursor = _execute(con, _sql("SELECT DISTINCT object_id FROM webhook_events WHERE owner_id=?"), (athlete_id,))
        existing_ids = {row["object_id"] for row in cursor.fetchall()}

        ride_types = {"Ride", "VirtualRide", "EBikeRide"}
        queued_count = 0
        skipped_count = 0
        now = int(time.time())

        for act in activities:
            act_id = act.get("id")
            sport_type = act.get("sport_type") or act.get("type")
            if sport_type not in ride_types or act_id in existing_ids:
                skipped_count += 1
                continue
            _execute(con,
                _sql("INSERT INTO webhook_events(received_at, object_id, owner_id, aspect_type, object_type, subscription_id, updates_json) VALUES (?,?,?,?,?,?,?)"),
                (now, act_id, athlete_id, "create", "activity", 0, "{}"),
            )
            queued_count += 1

        con.commit()
        log.info("Backfill for athlete %s: queued=%d skipped=%d total=%d", athlete_id, queued_count, skipped_count, len(activities))
        return {"ok": True, "total_fetched": len(activities), "queued": queued_count, "skipped": skipped_count}
    finally:
        close_connection(con)


@app.get("/api/reports")
def list_reports(request: Request):
    athlete_id = get_current_athlete(request)
    con = connect(s.db_path)
    try:
        rides = list_ride_analyses_chronological(con, athlete_id=athlete_id)
        progress = list_progress_summaries_chronological(con, athlete_id=athlete_id)

        items = []
        for r in rides:
            act = r.get("activity") or {}
            items.append({
                "kind": "ride", "activity_id": r["activity_id"], "created_at": r["created_at"],
                "model": r.get("model"), "prompt_version": r.get("prompt_version"),
                "name": act.get("name"), "start_date": act.get("start_date"), "sport_type": act.get("sport_type"),
            })
        for p in progress:
            created_at = int(p.get("created_at") or 0)
            date_str = time.strftime("%d/%m/%Y", time.localtime(created_at)) if created_at else ""
            items.append({
                "kind": "progress", "activity_id": p["activity_id"], "created_at": p["created_at"],
                "model": p.get("model"), "prompt_version": p.get("prompt_version"),
                "name": f"Progress - {date_str}".strip() or "Progress", "start_date": None, "sport_type": None,
            })

        items.sort(key=lambda x: x["created_at"] or 0, reverse=True)
        return {"items": items}
    finally:
        close_connection(con)


@app.get("/api/reports/{kind}/{activity_id}")
def get_report(kind: str, activity_id: int, request: Request):
    athlete_id = get_current_athlete(request)
    con = connect(s.db_path)
    try:
        if kind == "ride":
            r = get_ride_analysis(con, activity_id, athlete_id=athlete_id)
            if not r:
                raise HTTPException(status_code=404, detail="Ride report not found")
            return {"kind": "ride", "activity_id": r["activity_id"], "created_at": r["created_at"],
                    "model": r.get("model"), "prompt_version": r.get("prompt_version"), "markdown": r.get("narrative") or ""}
        if kind == "progress":
            p = get_progress_summary(con, activity_id, athlete_id=athlete_id)
            if not p:
                raise HTTPException(status_code=404, detail="Progress report not found")
            return {"kind": "progress", "activity_id": p["activity_id"], "created_at": p["created_at"],
                    "model": p.get("model"), "prompt_version": p.get("prompt_version"), "markdown": p.get("summary") or ""}
        raise HTTPException(status_code=400, detail="Invalid kind (expected 'ride' or 'progress')")
    finally:
        close_connection(con)
