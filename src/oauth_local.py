# src/oauth_local.py
from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import requests

from .config import get_settings
from .db import connect, init_db, upsert_tokens

AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"


class _Handler(BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        if "code" in qs:
            _Handler.code = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK. You can close this tab.")
        else:
            self.send_response(400)
            self.end_headers()


def run_oauth():
    s = get_settings()
    con = connect(s.db_path)
    init_db(con)

    redirect = urlparse(s.redirect_uri)
    host = redirect.hostname or "localhost"
    port = redirect.port or 8787

    httpd = HTTPServer((host, port), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    # Required for private activities + streams
    scopes = "activity:read_all"

    url = (
        f"{AUTH_URL}?client_id={s.client_id}"
        f"&redirect_uri={s.redirect_uri}"
        f"&response_type=code"
        f"&approval_prompt=force"
        f"&scope={scopes}"
    )

    print("Opening browser for Strava OAuth…")
    webbrowser.open(url)

    while _Handler.code is None:
        pass

    httpd.shutdown()

    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": s.client_id,
            "client_secret": s.client_secret,
            "code": _Handler.code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    r.raise_for_status()
    tok = r.json()

    athlete_id = tok["athlete"]["id"]
    upsert_tokens(con, athlete_id, tok["access_token"], tok["refresh_token"], tok["expires_at"])
    print(f"✅ Stored tokens for athlete_id={athlete_id} in {s.db_path}")


if __name__ == "__main__":
    run_oauth()