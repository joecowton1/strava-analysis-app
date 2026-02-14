import json
import os
import time
from typing import Optional

# Support both SQLite and PostgreSQL
USE_POSTGRES = os.environ.get("USE_POSTGRES", "false").lower() in ("true", "1", "yes")

if USE_POSTGRES:
    import psycopg2  # type: ignore[import-untyped]
    from psycopg2.extras import RealDictCursor  # type: ignore[import-untyped]
    from psycopg2.pool import SimpleConnectionPool  # type: ignore[import-untyped]
    
    _pool = None
    
    def connect(db_path: str = None):
        """Connect to PostgreSQL using connection string from environment."""
        global _pool
        
        # db_path is ignored for PostgreSQL - use DATABASE_URL instead
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable required for PostgreSQL")
        
        # Create connection pool if not exists
        if _pool is None:
            _pool = SimpleConnectionPool(1, 20, db_url)
        
        return _pool.getconn()
    
    def close_connection(con):
        """Return connection to pool."""
        if _pool and con:
            _pool.putconn(con)
    
else:
    import sqlite3
    from pathlib import Path
    
    def connect(db_path: str):
        """Connect to SQLite database."""
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        return con
    
    def close_connection(con):
        """Close SQLite connection."""
        if con:
            con.close()


def init_db(con) -> None:
    """Initialize database schema (works for both SQLite and PostgreSQL)."""
    
    if USE_POSTGRES:
        cursor = con.cursor()
        
        # PostgreSQL schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
              athlete_id BIGINT PRIMARY KEY,
              access_token TEXT NOT NULL,
              refresh_token TEXT NOT NULL,
              expires_at BIGINT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
              id SERIAL PRIMARY KEY,
              received_at BIGINT NOT NULL,
              subscription_id INTEGER,
              owner_id BIGINT,
              object_type TEXT,
              object_id BIGINT,
              aspect_type TEXT,
              event_time BIGINT,
              updates_json TEXT,
              status TEXT NOT NULL DEFAULT 'queued',
              attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
              activity_id BIGINT PRIMARY KEY,
              athlete_id BIGINT,
              raw_json TEXT,
              updated_at BIGINT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_streams (
              activity_id BIGINT PRIMARY KEY,
              streams_json TEXT NOT NULL,
              updated_at BIGINT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ride_analysis (
              activity_id BIGINT PRIMARY KEY,
              athlete_id BIGINT,
              created_at BIGINT NOT NULL,
              model TEXT,
              prompt_version TEXT,
              metrics_json TEXT NOT NULL,
              narrative_md TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress_summaries (
              activity_id BIGINT PRIMARY KEY,
              athlete_id BIGINT,
              created_at BIGINT NOT NULL,
              model TEXT,
              prompt_version TEXT,
              summary_md TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowed_athletes (
              athlete_id BIGINT PRIMARY KEY,
              name TEXT,
              added_at BIGINT NOT NULL
            )
        """)

        # --- Migrations for existing tables (idempotent) ---
        # Add athlete_id column if missing
        for tbl in ("ride_analysis", "progress_summaries"):
            cursor.execute(f"""
                DO $$ BEGIN
                    ALTER TABLE {tbl} ADD COLUMN athlete_id BIGINT;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
        # Backfill athlete_id from activities table
        cursor.execute("""
            UPDATE ride_analysis SET athlete_id = a.athlete_id
            FROM activities a
            WHERE ride_analysis.activity_id = a.activity_id
              AND ride_analysis.athlete_id IS NULL
        """)
        cursor.execute("""
            UPDATE progress_summaries SET athlete_id = a.athlete_id
            FROM activities a
            WHERE progress_summaries.activity_id = a.activity_id
              AND progress_summaries.athlete_id IS NULL
        """)

        # Seed allowed_athletes from env var (comma-separated list)
        import os as _os
        _allowed = _os.environ.get("ALLOWED_ATHLETES", "")
        if _allowed:
            for _aid_str in _allowed.split(","):
                _aid_str = _aid_str.strip()
                if _aid_str.isdigit():
                    cursor.execute(
                        """INSERT INTO allowed_athletes(athlete_id, name, added_at)
                           VALUES(%s, NULL, %s)
                           ON CONFLICT(athlete_id) DO NOTHING""",
                        (int(_aid_str), int(time.time())),
                    )

        con.commit()
        cursor.close()
        
    else:
        # SQLite schema (original)
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
          athlete_id INTEGER,
          created_at INTEGER NOT NULL,
          model TEXT,
          prompt_version TEXT,
          metrics_json TEXT NOT NULL,
          narrative_md TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS progress_summaries (
          activity_id INTEGER PRIMARY KEY,
          athlete_id INTEGER,
          created_at INTEGER NOT NULL,
          model TEXT,
          prompt_version TEXT,
          summary_md TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS allowed_athletes (
          athlete_id INTEGER PRIMARY KEY,
          name TEXT,
          added_at INTEGER NOT NULL
        );
        """)
        con.commit()


def _dict_from_row(row) -> dict:
    """Convert database row to dict (works for both SQLite and PostgreSQL)."""
    if USE_POSTGRES:
        return dict(row) if row else None
    else:
        return dict(row) if row else None


def upsert_tokens(con, athlete_id: int, access_token: str, refresh_token: str, expires_at: int) -> None:
    if USE_POSTGRES:
        cursor = con.cursor()
        cursor.execute(
            """
            INSERT INTO tokens(athlete_id, access_token, refresh_token, expires_at)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(athlete_id) DO UPDATE SET
              access_token=EXCLUDED.access_token,
              refresh_token=EXCLUDED.refresh_token,
              expires_at=EXCLUDED.expires_at
            """,
            (athlete_id, access_token, refresh_token, int(expires_at)),
        )
        con.commit()
        cursor.close()
    else:
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
    if USE_POSTGRES:
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM tokens WHERE athlete_id=%s", (athlete_id,))
        row = cursor.fetchone()
        cursor.close()
        return dict(row) if row else None
    else:
        row = con.execute("SELECT * FROM tokens WHERE athlete_id=?", (athlete_id,)).fetchone()
        return dict(row) if row else None


def save_ride_analysis(con, activity_id: int, metrics: dict, narrative: str, model: str = "gpt-4o-mini", prompt_version: str = "1.0", athlete_id: int | None = None) -> None:
    """Save AI analysis of a ride to the database."""
    now = int(time.time())
    
    if USE_POSTGRES:
        cursor = con.cursor()
        cursor.execute(
            """
            INSERT INTO ride_analysis(activity_id, athlete_id, created_at, model, prompt_version, metrics_json, narrative_md)
            VALUES(%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(activity_id) DO UPDATE SET
              athlete_id=EXCLUDED.athlete_id,
              created_at=EXCLUDED.created_at,
              model=EXCLUDED.model,
              prompt_version=EXCLUDED.prompt_version,
              metrics_json=EXCLUDED.metrics_json,
              narrative_md=EXCLUDED.narrative_md
            """,
            (activity_id, athlete_id, now, model, prompt_version, json.dumps(metrics), narrative),
        )
        con.commit()
        cursor.close()
    else:
        con.execute(
            """
            INSERT INTO ride_analysis(activity_id, athlete_id, created_at, model, prompt_version, metrics_json, narrative_md)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET
              athlete_id=excluded.athlete_id,
              created_at=excluded.created_at,
              model=excluded.model,
              prompt_version=excluded.prompt_version,
              metrics_json=excluded.metrics_json,
              narrative_md=excluded.narrative_md
            """,
            (activity_id, athlete_id, now, model, prompt_version, json.dumps(metrics), narrative),
        )
        con.commit()


def get_ride_analysis(con, activity_id: int, athlete_id: int | None = None):
    """Get ride analysis from database, optionally scoped to an athlete."""
    if athlete_id is not None:
        q = "SELECT * FROM ride_analysis WHERE activity_id={ph} AND athlete_id={ph}"
        params = (activity_id, athlete_id)
    else:
        q = "SELECT * FROM ride_analysis WHERE activity_id={ph}"
        params = (activity_id,)

    if USE_POSTGRES:
        q = q.replace("{ph}", "%s")
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute(q, params)
        row = cursor.fetchone()
        cursor.close()
    else:
        q = q.replace("{ph}", "?")
        row = con.execute(q, params).fetchone()
    
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


def list_ride_analyses_chronological(con, athlete_id: int | None = None):
    """List ride analyses in chronological order with activity context if available."""
    where = ""
    params: tuple = ()
    if athlete_id is not None:
        if USE_POSTGRES:
            where = "WHERE ra.athlete_id = %s"
        else:
            where = "WHERE ra.athlete_id = ?"
        params = (athlete_id,)

    q = f"""
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
        {where}
        ORDER BY ra.created_at ASC
    """

    if USE_POSTGRES:
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute(q, params)
        rows = cursor.fetchall()
        cursor.close()
    else:
        rows = con.execute(q, params).fetchall()

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
    athlete_id: int | None = None,
) -> None:
    """Save progress summary (aggregated across athlete's rides) as-of a given activity."""
    now = int(time.time())

    if USE_POSTGRES:
        cursor = con.cursor()
        cursor.execute(
            """
            INSERT INTO progress_summaries(activity_id, athlete_id, created_at, model, prompt_version, summary_md)
            VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT(activity_id) DO UPDATE SET
              athlete_id=EXCLUDED.athlete_id,
              created_at=EXCLUDED.created_at,
              model=EXCLUDED.model,
              prompt_version=EXCLUDED.prompt_version,
              summary_md=EXCLUDED.summary_md
            """,
            (activity_id, athlete_id, now, model, prompt_version, summary_md),
        )
        con.commit()
        cursor.close()
    else:
        con.execute(
            """
            INSERT INTO progress_summaries(activity_id, athlete_id, created_at, model, prompt_version, summary_md)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET
              athlete_id=excluded.athlete_id,
              created_at=excluded.created_at,
              model=excluded.model,
              prompt_version=excluded.prompt_version,
              summary_md=excluded.summary_md
            """,
            (activity_id, athlete_id, now, model, prompt_version, summary_md),
        )
        con.commit()


def get_progress_summary(con, activity_id: int, athlete_id: int | None = None):
    if athlete_id is not None:
        q = "SELECT * FROM progress_summaries WHERE activity_id={ph} AND athlete_id={ph}"
        params = (activity_id, athlete_id)
    else:
        q = "SELECT * FROM progress_summaries WHERE activity_id={ph}"
        params = (activity_id,)

    if USE_POSTGRES:
        q = q.replace("{ph}", "%s")
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute(q, params)
        row = cursor.fetchone()
        cursor.close()
    else:
        q = q.replace("{ph}", "?")
        row = con.execute(q, params).fetchone()
    
    if not row:
        return None
    return {
        "activity_id": row["activity_id"],
        "created_at": row["created_at"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "summary": row["summary_md"],
    }


def list_progress_summaries_chronological(con, athlete_id: int | None = None):
    """List progress summaries in chronological order with activity context if available."""
    where = ""
    params: tuple = ()
    if athlete_id is not None:
        if USE_POSTGRES:
            where = "WHERE ps.athlete_id = %s"
        else:
            where = "WHERE ps.athlete_id = ?"
        params = (athlete_id,)

    q = f"""
        SELECT
          ps.activity_id,
          ps.created_at,
          ps.model,
          ps.prompt_version,
          ps.summary_md,
          a.raw_json AS activity_raw_json
        FROM progress_summaries ps
        LEFT JOIN activities a ON a.activity_id = ps.activity_id
        {where}
        ORDER BY ps.created_at ASC
    """

    if USE_POSTGRES:
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute(q, params)
        rows = cursor.fetchall()
        cursor.close()
    else:
        rows = con.execute(q, params).fetchall()

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


def is_athlete_allowed(con, athlete_id: int) -> bool:
    """Check if an athlete is in the allowed_athletes table."""
    if USE_POSTGRES:
        cursor = con.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT 1 FROM allowed_athletes WHERE athlete_id=%s", (athlete_id,))
        row = cursor.fetchone()
        cursor.close()
    else:
        row = con.execute("SELECT 1 FROM allowed_athletes WHERE athlete_id=?", (athlete_id,)).fetchone()
    return row is not None
