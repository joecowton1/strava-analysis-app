import json, sqlite3
from pathlib import Path

def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con

def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS tokens (
      athlete_id INTEGER PRIMARY KEY,
      access_token TEXT NOT NULL,
      refresh_token TEXT NOT NULL,
      expires_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS webhook_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      received_at INTEGER NOT NULL,
      subscription_id INTEGER,
      owner_id INTEGER,
      object_type TEXT,
      object_id INTEGER,
      aspect_type TEXT,
      event_time INTEGER,
      updates_json TEXT,
      status TEXT NOT NULL DEFAULT 'queued',
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT
    );
    CREATE TABLE IF NOT EXISTS activities (
      activity_id INTEGER PRIMARY KEY,
      athlete_id INTEGER,
      raw_json TEXT,
      updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS activity_streams (
      activity_id INTEGER PRIMARY KEY,
      streams_json TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ride_analysis (
      activity_id INTEGER PRIMARY KEY,
      created_at INTEGER NOT NULL,
      model TEXT,
      prompt_version TEXT,
      metrics_json TEXT NOT NULL,
      narrative_md TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS progress_summaries (
      activity_id INTEGER PRIMARY KEY,
      created_at INTEGER NOT NULL,
      model TEXT,
      prompt_version TEXT,
      summary_md TEXT NOT NULL
    );
    """)
    con.commit()

def upsert_tokens(con, athlete_id: int, access_token: str, refresh_token: str, expires_at: int) -> None:
    con.execute(
        """
        INSERT INTO tokens(athlete_id, access_token, refresh_token, expires_at)
        VALUES(?,?,?,?)
        ON CONFLICT(athlete_id) DO UPDATE SET
          access_token=excluded.access_token,
          refresh_token=excluded.refresh_token,
          expires_at=excluded.expires_at
        """,
        (athlete_id, access_token, refresh_token, int(expires_at)),
    )
    con.commit()

def get_tokens(con, athlete_id: int):
    row = con.execute("SELECT * FROM tokens WHERE athlete_id=?", (athlete_id,)).fetchone()
    return dict(row) if row else None

def save_ride_analysis(con, activity_id: int, metrics: dict, narrative: str, model: str = "gpt-4o-mini", prompt_version: str = "1.0") -> None:
    """Save AI analysis of a ride to the database."""
    import json
    import time
    
    con.execute(
        """
        INSERT INTO ride_analysis(activity_id, created_at, model, prompt_version, metrics_json, narrative_md)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
          created_at=excluded.created_at,
          model=excluded.model,
          prompt_version=excluded.prompt_version,
          metrics_json=excluded.metrics_json,
          narrative_md=excluded.narrative_md
        """,
        (activity_id, int(time.time()), model, prompt_version, json.dumps(metrics), narrative),
    )
    con.commit()

def get_ride_analysis(con, activity_id: int):
    """Get ride analysis from database."""
    row = con.execute("SELECT * FROM ride_analysis WHERE activity_id=?", (activity_id,)).fetchone()
    if not row:
        return None
    
    return {
        "activity_id": row["activity_id"],
        "created_at": row["created_at"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "metrics": json.loads(row["metrics_json"]),
        "narrative": row["narrative_md"]
    }


def list_ride_analyses_chronological(con):
    """List ride analyses in chronological order with activity context if available."""
    rows = con.execute(
        """
        SELECT
          ra.activity_id,
          ra.created_at,
          ra.model,
          ra.prompt_version,
          ra.metrics_json,
          ra.narrative_md,
          a.raw_json AS activity_raw_json
        FROM ride_analysis ra
        LEFT JOIN activities a ON a.activity_id = ra.activity_id
        ORDER BY ra.created_at ASC
        """
    ).fetchall()

    out = []
    for r in rows:
        activity = None
        if r["activity_raw_json"]:
            try:
                activity = json.loads(r["activity_raw_json"])
            except Exception:
                activity = None

        out.append(
            {
                "activity_id": r["activity_id"],
                "created_at": r["created_at"],
                "model": r["model"],
                "prompt_version": r["prompt_version"],
                "metrics": json.loads(r["metrics_json"]),
                "narrative": r["narrative_md"],
                "activity": activity,
            }
        )
    return out


def save_progress_summary(
    con,
    activity_id: int,
    summary_md: str,
    model: str = "gpt-4o-mini",
    prompt_version: str = "progress_v1",
) -> None:
    """Save progress summary (aggregated across all rides) as-of a given activity."""
    import time

    con.execute(
        """
        INSERT INTO progress_summaries(activity_id, created_at, model, prompt_version, summary_md)
        VALUES(?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
          created_at=excluded.created_at,
          model=excluded.model,
          prompt_version=excluded.prompt_version,
          summary_md=excluded.summary_md
        """,
        (activity_id, int(time.time()), model, prompt_version, summary_md),
    )
    con.commit()


def get_progress_summary(con, activity_id: int):
    row = con.execute("SELECT * FROM progress_summaries WHERE activity_id=?", (activity_id,)).fetchone()
    if not row:
        return None
    return {
        "activity_id": row["activity_id"],
        "created_at": row["created_at"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "summary": row["summary_md"],
    }


def list_progress_summaries_chronological(con):
    """List progress summaries in chronological order with activity context if available."""
    rows = con.execute(
        """
        SELECT
          ps.activity_id,
          ps.created_at,
          ps.model,
          ps.prompt_version,
          ps.summary_md,
          a.raw_json AS activity_raw_json
        FROM progress_summaries ps
        LEFT JOIN activities a ON a.activity_id = ps.activity_id
        ORDER BY ps.created_at ASC
        """
    ).fetchall()

    out = []
    for r in rows:
        activity = None
        if r["activity_raw_json"]:
            try:
                activity = json.loads(r["activity_raw_json"])
            except Exception:
                activity = None
        out.append(
            {
                "activity_id": r["activity_id"],
                "created_at": r["created_at"],
                "model": r["model"],
                "prompt_version": r["prompt_version"],
                "summary": r["summary_md"],
                "activity": activity,
            }
        )
    return out
