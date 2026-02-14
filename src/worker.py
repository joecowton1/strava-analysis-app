import os
import time
import json
import re
from pathlib import Path
import requests
from .config import get_settings
from .db import (
    connect,
    init_db,
    save_ride_analysis,
    get_ride_analysis,
    upsert_tokens,
    list_ride_analyses_chronological,
    save_progress_summary,
)
from .strava_client import StravaClient

WORKER_VERSION = "dual_output_md_pdf_v1"

s = get_settings()
con = connect(s.db_path)
init_db(con)
client = StravaClient(s.client_id, s.client_secret)

# Ensure output directories exist
Path(s.report_output_dir).mkdir(parents=True, exist_ok=True)
Path(s.pdf_output_dir).mkdir(parents=True, exist_ok=True)

# Worker runtime knobs (env only; kept out of Settings to avoid widening config surface area)
POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "2"))
HEARTBEAT_SECONDS = float(os.environ.get("WORKER_HEARTBEAT_SECONDS", "60"))
TOKEN_REFRESH_SKEW_SECONDS = int(os.environ.get("TOKEN_REFRESH_SKEW_SECONDS", "60"))

# Try to import ride analyzer (optional - won't fail if OpenAI not configured)
try:
    from .ride_analyzer import analyze_ride
    AI_ANALYSIS_ENABLED = bool(s.openai_api_key)
except (ImportError, AttributeError):
    AI_ANALYSIS_ENABLED = False
    analyze_ride = None

from .markdown_generator import generate_ride_markdown

# Optional: progress summarizer (second OpenAI call)
try:
    from .progress_summarizer import summarize_progress
    PROGRESS_SUMMARY_ENABLED = os.environ.get("PROGRESS_SUMMARY_ENABLED", "1") not in ("0", "false", "False")
except Exception:
    summarize_progress = None
    PROGRESS_SUMMARY_ENABLED = False

# Try to import PDF generator (optional)
try:
    from .pdf_generator import generate_ride_pdf, REPORTLAB_AVAILABLE
    PDF_GENERATION_ENABLED = REPORTLAB_AVAILABLE
except (ImportError, AttributeError):
    PDF_GENERATION_ENABLED = False
    generate_ride_pdf = None

if AI_ANALYSIS_ENABLED:
    print("AI ride analysis enabled")
else:
    print("AI ride analysis disabled (OPENAI_API_KEY not set)")

print("Markdown report generation enabled", flush=True)
if PDF_GENERATION_ENABLED:
    print("PDF generation enabled", flush=True)
else:
    print("PDF generation disabled (reportlab not installed)", flush=True)
if PROGRESS_SUMMARY_ENABLED and summarize_progress:
    print("Progress summary enabled", flush=True)
else:
    print("Progress summary disabled", flush=True)

print(f"WORKER_VERSION: {WORKER_VERSION}", flush=True)
print(f"DB_PATH: {Path(s.db_path).resolve()}", flush=True)
print(f"REPORT_OUTPUT_DIR: {Path(s.report_output_dir).resolve()}", flush=True)
print(f"PDF_OUTPUT_DIR: {Path(s.pdf_output_dir).resolve()}", flush=True)
print("Worker running", flush=True)

_last_heartbeat = 0.0

def _heartbeat_if_needed() -> None:
    global _last_heartbeat
    now = time.time()
    if now - _last_heartbeat < HEARTBEAT_SECONDS:
        return
    _last_heartbeat = now
    queued = con.execute("SELECT COUNT(*) AS c FROM webhook_events WHERE status='queued'").fetchone()["c"]
    failed = con.execute("SELECT COUNT(*) AS c FROM webhook_events WHERE status='failed'").fetchone()["c"]
    processing = con.execute("SELECT COUNT(*) AS c FROM webhook_events WHERE status='processing'").fetchone()["c"]
    # Always print occasionally so it's obvious the worker is alive.
    print(f"[heartbeat] queued={queued} processing={processing} failed={failed}", flush=True)

def _refresh_access_token_for_athlete(athlete_id: int, refresh_token: str) -> str:
    new_tokens = client.refresh_access_token(refresh_token)
    upsert_tokens(
        con,
        athlete_id,
        new_tokens["access_token"],
        new_tokens["refresh_token"],
        new_tokens["expires_at"],
    )
    return new_tokens["access_token"]

while True:
    ev = con.execute("SELECT * FROM webhook_events WHERE status='queued' LIMIT 1").fetchone()
    if not ev:
        _heartbeat_if_needed()
        time.sleep(POLL_SECONDS)
        continue

    print(
        f"Picked event id={ev['id']} object_id={ev['object_id']} owner_id={ev['owner_id']} aspect_type={ev['aspect_type']}",
        flush=True,
    )
    con.execute("UPDATE webhook_events SET status='processing' WHERE id=?", (ev["id"],))
    con.commit()

    try:
        tok = con.execute("SELECT * FROM tokens WHERE athlete_id=?", (ev["owner_id"],)).fetchone()
        if not tok:
            raise RuntimeError("No OAuth token for athlete")

        # Proactively refresh access token if close to expiry.
        access = tok["access_token"]
        now_ts = int(time.time())
        if tok["expires_at"] <= now_ts + TOKEN_REFRESH_SKEW_SECONDS:
            access = _refresh_access_token_for_athlete(ev["owner_id"], tok["refresh_token"])

        # Fetch activity/streams; if we get a 401, refresh token and retry once.
        try:
            act = client.get_activity(access, ev["object_id"])
            streams = client.get_activity_streams(access, ev["object_id"])
        except requests.HTTPError as http_err:
            status = getattr(http_err.response, "status_code", None)
            if status == 401:
                access = _refresh_access_token_for_athlete(ev["owner_id"], tok["refresh_token"])
                act = client.get_activity(access, ev["object_id"])
                streams = client.get_activity_streams(access, ev["object_id"])
            else:
                raise

        now = int(time.time())
        con.execute(
            "INSERT OR REPLACE INTO activities(activity_id, athlete_id, raw_json, updated_at) VALUES (?,?,?,?)",
            (ev["object_id"], ev["owner_id"], json.dumps(act), now),
        )
        con.execute(
            "INSERT OR REPLACE INTO activity_streams(activity_id, streams_json, updated_at) VALUES (?,?,?)",
            (ev["object_id"], json.dumps(streams), now),
        )
        con.commit()
        
        # Generate AI analysis if enabled and it's a ride
        if AI_ANALYSIS_ENABLED and analyze_ride and act.get("sport_type") in ["Ride", "VirtualRide", "EBikeRide"]:
            try:
                print(f"Analyzing ride {ev['object_id']}...", flush=True)
                analysis = analyze_ride(act, streams)
                used_model = analysis.get("model") or s.openai_model
                print(f"✓ OpenAI model used: {used_model}", flush=True)
                save_ride_analysis(
                    con,
                    ev["object_id"],
                    analysis["metrics"],
                    analysis["narrative"],
                    model=used_model,
                    prompt_version=analysis.get("prompt_version", "fred_v3")
                )
                print(f"✓ Analysis complete for {ev['object_id']}", flush=True)
                
                # Generate markdown + PDF after analysis is saved
                try:
                    analysis_data = get_ride_analysis(con, ev["object_id"])
                    if analysis_data:
                        # Create filename with ride name and prompt version (sanitized for filesystem)
                        ride_name = act.get("name", "Untitled_Ride")
                        prompt_version = analysis_data.get("prompt_version", "v1")
                        # Sanitize filename: replace spaces and special chars, keep alphanumeric and underscores
                        safe_name = "".join(c if c.isalnum() or c == '_' else '_' for c in ride_name)
                        safe_name = re.sub(r'_+', '_', safe_name)  # Replace multiple underscores with single
                        safe_name = safe_name.strip('_')  # Remove leading/trailing underscores
                        safe_name = safe_name[:50] if safe_name else "Ride"  # Limit length
                        # Sanitize prompt version
                        safe_version = "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in prompt_version)
                        safe_version = re.sub(r'_+', '_', safe_version).strip('_')

                        report_payload = {
                            "metrics": analysis_data["metrics"],
                            "narrative": analysis_data["narrative"],
                        }

                        md_filename = f"{safe_name}_{safe_version}_{ev['object_id']}.md"
                        md_path = Path(s.report_output_dir) / md_filename
                        generate_ride_markdown(act, report_payload, str(md_path))
                        print(f"✓ Markdown generated: {md_path}", flush=True)

                        info_parts = [f"md={md_path}"]

                        if PDF_GENERATION_ENABLED and generate_ride_pdf:
                            pdf_filename = f"{safe_name}_{safe_version}_{ev['object_id']}.pdf"
                            pdf_path = Path(s.pdf_output_dir) / pdf_filename
                            generate_ride_pdf(act, report_payload, str(pdf_path))
                            print(f"✓ PDF generated: {pdf_path}", flush=True)
                            info_parts.append(f"pdf={pdf_path}")

                        # Persist success info so we can debug without relying on stdout.
                        try:
                            con.execute(
                                "UPDATE webhook_events SET last_error=? WHERE id=?",
                                ("report_generated: " + " ".join(info_parts), ev["id"]),
                            )
                            con.commit()
                        except Exception:
                            pass
                except Exception as md_error:
                    msg = f"report_generation_failed: {md_error}"
                    print(f"⚠ Report generation failed for {ev['object_id']}: {md_error}", flush=True)
                    # Persist the error so we can debug without relying on stdout.
                    try:
                        con.execute("UPDATE webhook_events SET last_error=? WHERE id=?", (msg, ev["id"]))
                        con.commit()
                    except Exception:
                        # Don't fail ingestion if even error persistence fails.
                        pass

                # Second OpenAI call: summarize progress across all reports (chronological)
                if PROGRESS_SUMMARY_ENABLED and summarize_progress:
                    try:
                        all_analyses = list_ride_analyses_chronological(con)
                        progress = summarize_progress(all_analyses)
                        used_ps_model = progress.get("model") or s.openai_model
                        print(f"✓ Progress summary model used: {used_ps_model}", flush=True)
                        save_progress_summary(
                            con,
                            ev["object_id"],
                            progress["summary_md"],
                            model=used_ps_model,
                            prompt_version=progress.get("prompt_version", "progress_v1"),
                        )

                        ps_version = progress.get("prompt_version", "progress_v1")
                        safe_ps_version = "".join(
                            c if c.isalnum() or c in ("_", "-", ".") else "_" for c in ps_version
                        )
                        safe_ps_version = re.sub(r"_+", "_", safe_ps_version).strip("_")

                        # Use the current date (local time) in the filename instead of the last ride name.
                        # Keep activity_id to avoid collisions if multiple summaries are generated on the same day.
                        date_str = time.strftime("%Y-%m-%d", time.localtime())

                        ps_base = f"Progress_Summary_{date_str}_{safe_ps_version}_{ev['object_id']}"

                        ps_md_path = Path(s.report_output_dir) / f"{ps_base}.md"
                        ps_md_path.write_text(progress["summary_md"], encoding="utf-8")
                        print(f"✓ Progress summary markdown generated: {ps_md_path}", flush=True)

                        if PDF_GENERATION_ENABLED and generate_ride_pdf:
                            ps_pdf_path = Path(s.pdf_output_dir) / f"{ps_base}.pdf"
                            generate_ride_pdf(
                                act,
                                {"metrics": {"type": "progress_summary"}, "narrative": progress["summary_md"]},
                                str(ps_pdf_path),
                            )
                            print(f"✓ Progress summary PDF generated: {ps_pdf_path}", flush=True)
                    except Exception as ps_error:
                        print(f"⚠ Progress summary failed for {ev['object_id']}: {ps_error}", flush=True)
            except Exception as analysis_error:
                print(f"⚠ Analysis failed for {ev['object_id']}: {analysis_error}", flush=True)
                # Don't fail the whole ingestion if analysis fails
        else:
            if act.get("sport_type") not in ["Ride", "VirtualRide", "EBikeRide"]:
                print(f"Skipping analysis (sport_type={act.get('sport_type')})", flush=True)
            elif not AI_ANALYSIS_ENABLED:
                print("Skipping analysis (OPENAI_API_KEY not set)", flush=True)
            elif not analyze_ride:
                print("Skipping analysis (ride_analyzer import failed)", flush=True)
        
        con.execute("UPDATE webhook_events SET status='done' WHERE id=?", (ev["id"],))
        con.commit()
        print("Ingested", ev["object_id"], flush=True)
    except Exception as e:
        con.execute("UPDATE webhook_events SET status='failed', last_error=? WHERE id=?", (str(e), ev["id"]))
        con.commit()
        print("Failed", e, flush=True)
