#!/usr/bin/env python3
"""
Test script to manually trigger analysis for an existing activity.
"""
import json
import re
from src.config import get_settings
from src.db import connect
from src.strava_client import StravaClient
from src.ride_analyzer import analyze_ride
from src.db import save_ride_analysis, get_ride_analysis
from src.markdown_generator import generate_ride_markdown
from src.pdf_generator import generate_ride_pdf, REPORTLAB_AVAILABLE
from pathlib import Path

s = get_settings()
con = connect(s.db_path)

# Get activity from database
activity_id = 16944846767
row = con.execute('SELECT raw_json, athlete_id FROM activities WHERE activity_id = ?', (activity_id,)).fetchone()

if not row:
    print(f"Activity {activity_id} not found in database")
    exit(1)

act = json.loads(row['raw_json'])
athlete_id = row['athlete_id']

print(f"Activity: {act.get('name')}")
print(f"Sport Type: {act.get('sport_type')}")
print(f"Athlete ID: {athlete_id}")

# Check if it's a ride type
if act.get("sport_type") not in ["Ride", "VirtualRide", "EBikeRide"]:
    print(f"⚠ This is not a ride type (sport_type: {act.get('sport_type')}). Analysis only runs for Ride/VirtualRide/EBikeRide.")
    exit(1)

# Check if OpenAI is configured
if not s.openai_api_key:
    print("⚠ OPENAI_API_KEY is not set. Cannot generate analysis.")
    exit(1)

print("\nFetching streams...")
# Get tokens and fetch streams
tok = con.execute("SELECT * FROM tokens WHERE athlete_id=?", (athlete_id,)).fetchone()
if not tok:
    print("⚠ No OAuth token found for athlete")
    exit(1)

client = StravaClient(s.client_id, s.client_secret)
access = tok["access_token"]

try:
    streams = client.get_activity_streams(access, activity_id)
    print("✓ Streams fetched")
except Exception as e:
    print(f"⚠ Could not fetch streams: {e}")
    streams = None

print("\nGenerating analysis...")
try:
    analysis = analyze_ride(act, streams)
    print("✓ Analysis generated")
    print(f"Metrics keys: {list(analysis['metrics'].keys())}")
    print(f"Narrative preview: {analysis['narrative'][:200]}...")
    
    # Save analysis
    save_ride_analysis(
        con,
        activity_id,
        analysis["metrics"],
        analysis["narrative"],
        model=s.openai_model,
        prompt_version=analysis.get("prompt_version", "fred_v3"),
    )
    print("✓ Analysis saved to database")
    
    # Generate Markdown + PDF reports
    print("\nGenerating markdown report...")
    ride_name = act.get("name", "Untitled_Ride")
    prompt_version = analysis.get("prompt_version", "v1")
    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in ride_name)
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")
    safe_name = safe_name[:50] if safe_name else "Ride"
    safe_version = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in prompt_version)
    safe_version = re.sub(r"_+", "_", safe_version).strip("_")
    md_path = Path(s.report_output_dir) / f"{safe_name}_{safe_version}_{activity_id}.md"
    generate_ride_markdown(act, analysis, str(md_path))
    print(f"✓ Markdown generated: {md_path}")

    if REPORTLAB_AVAILABLE:
        print("\nGenerating PDF report...")
        pdf_path = Path(s.pdf_output_dir) / f"{safe_name}_{safe_version}_{activity_id}.pdf"
        generate_ride_pdf(act, analysis, str(pdf_path))
        print(f"✓ PDF generated: {pdf_path}")
    else:
        print("\nSkipping PDF (reportlab not installed)")
    
except Exception as e:
    print(f"⚠ Error: {e}")
    import traceback
    traceback.print_exc()

