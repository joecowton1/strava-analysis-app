#!/usr/bin/env bash
set -euo pipefail

# Run all local services:
# - FastAPI webhook server (uvicorn)
# - Worker (python -m src.worker)
# - React frontend (Vite)
#
# Usage:
#   ./scripts/run_all.sh
#
# Optional env vars:
#   WEB_PORT=8000
#   WEB_HOST=0.0.0.0
#   WEB_RELOAD=1            (set 0 to disable --reload)
#   VITE_PORT=5173
#   STRAVA_AUTH_MODE=prompt   (prompt|auto_oauth|auto_refresh)
#     - prompt: print what to run if tokens missing/expired (default)
#     - auto_refresh: run `python -m src.refresh_tokens` if tokens expired
#     - auto_oauth: run `python -m src.oauth_local` if no tokens

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-8000}"
WEB_RELOAD="${WEB_RELOAD:-1}"
VITE_PORT="${VITE_PORT:-5173}"
STRAVA_AUTH_MODE="${STRAVA_AUTH_MODE:-prompt}"

cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
else
  echo "WARN: .venv not found at $ROOT_DIR/.venv. Continuing without virtualenv."
fi

echo "[auth] Checking Strava OAuth tokens…"
python3 - << 'EOF' || true
import os, time, sqlite3
from pathlib import Path

db_path = os.environ.get("DB_PATH") or "./db/strava.sqlite"
db_path = str(Path(db_path))

try:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    # If table missing, treat as no tokens.
    try:
        row = con.execute("SELECT athlete_id, expires_at FROM tokens ORDER BY athlete_id LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        row = None

    now = int(time.time())
    if not row:
        print(f"[auth] No tokens found in {db_path}")
        raise SystemExit(2)

    expires_at = int(row["expires_at"])
    if expires_at <= now + 60:
        print(f"[auth] Tokens present but expired/expiring (athlete_id={row['athlete_id']}, expires_at={expires_at})")
        raise SystemExit(3)

    print(f"[auth] Tokens OK (athlete_id={row['athlete_id']}, expires_in={(expires_at-now)//60}m)")
finally:
    try:
        con.close()
    except Exception:
        pass
EOF

AUTH_STATUS=$?
if [[ "$AUTH_STATUS" != "0" ]]; then
  if [[ "$STRAVA_AUTH_MODE" == "auto_refresh" ]]; then
    echo "[auth] Attempting token refresh: python -m src.refresh_tokens"
    python -m src.refresh_tokens || true
  elif [[ "$STRAVA_AUTH_MODE" == "auto_oauth" ]]; then
    echo "[auth] Launching OAuth flow: python -m src.oauth_local"
    python -m src.oauth_local || true
  else
    echo "[auth] Tokens missing/expired. Run one of:"
    echo "  - python -m src.oauth_local   (interactive browser auth)"
    echo "  - python -m src.refresh_tokens (if refresh token is still valid)"
    echo "  Tip: set STRAVA_AUTH_MODE=auto_refresh or auto_oauth to automate."
  fi
fi

cleanup() {
  echo ""
  echo "Shutting down…"
  # Kill entire process group (includes children)
  kill -- -$$ 2>/dev/null || true
}
trap cleanup INT TERM

echo "Starting services from: $ROOT_DIR"
echo "FastAPI: http://${WEB_HOST}:${WEB_PORT}"
echo "Frontend: http://localhost:${VITE_PORT}"
echo ""

UVICORN_ARGS=(src.webhook_server:app --host "$WEB_HOST" --port "$WEB_PORT")
if [[ "$WEB_RELOAD" == "1" ]]; then
  UVICORN_ARGS+=(--reload)
fi

echo "[web] uvicorn ${UVICORN_ARGS[*]}"
uvicorn "${UVICORN_ARGS[@]}" &

echo "[worker] python -m src.worker"
python -m src.worker &

if [[ -d "frontend" ]]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[frontend] npm run dev (port ${VITE_PORT})"
    (
      cd "$ROOT_DIR/frontend"
      # Ensure dependencies are installed (best-effort; keeps script simple)
      if [[ ! -d "node_modules" ]]; then
        echo "[frontend] node_modules missing; running npm install…"
        npm install
      fi
      npm run dev -- --port "$VITE_PORT" --host
    ) &
  else
    echo "WARN: npm not found; skipping frontend."
  fi
else
  echo "WARN: frontend/ directory not found; skipping frontend."
fi

echo ""
echo "All services started. Press Ctrl+C to stop."
wait


