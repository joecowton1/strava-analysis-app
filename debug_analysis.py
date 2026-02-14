#!/usr/bin/env python3
"""
Debug script to check if ride analyses and PDFs are being created.
"""
import json
from pathlib import Path
from src.config import get_settings
from src.db import connect, get_ride_analysis

s = get_settings()
con = connect(s.db_path)

print("=" * 60)
print("RIDE ANALYSIS DEBUG")
print("=" * 60)

# Check for analyses in database
print("\n1. Checking ride_analysis table...")
analyses = con.execute("SELECT activity_id, created_at, model FROM ride_analysis ORDER BY created_at DESC LIMIT 10").fetchall()
print(f"   Found {len(analyses)} analyses in database")

if analyses:
    for row in analyses:
        print(f"   - Activity ID: {row['activity_id']}, Created: {row['created_at']}, Model: {row['model']}")
        
        # Try to get full analysis
        analysis = get_ride_analysis(con, row['activity_id'])
        if analysis:
            metrics_keys = list(analysis['metrics'].keys()) if analysis['metrics'] else []
            narrative_preview = analysis['narrative'][:100] if analysis['narrative'] else "No narrative"
            print(f"     Metrics keys: {metrics_keys}")
            print(f"     Narrative preview: {narrative_preview}...")
else:
    print("   No analyses found in database")

# Check for PDFs
print("\n2. Checking PDF directory...")
pdf_dir = Path(s.pdf_output_dir)
print(f"   PDF directory: {pdf_dir.absolute()}")
if pdf_dir.exists():
    pdfs = list(pdf_dir.glob("ride_*.pdf"))
    print(f"   Found {len(pdfs)} PDF files")
    for pdf in pdfs[:10]:
        size = pdf.stat().st_size
        print(f"   - {pdf.name} ({size} bytes)")
else:
    print(f"   PDF directory does not exist: {pdf_dir}")

# Check for activities
print("\n3. Checking activities table...")
activities = con.execute("SELECT activity_id, athlete_id, updated_at FROM activities ORDER BY updated_at DESC LIMIT 10").fetchall()
print(f"   Found {len(activities)} activities in database")
for row in activities[:5]:
    print(f"   - Activity ID: {row['activity_id']}, Athlete: {row['athlete_id']}, Updated: {row['updated_at']}")

# Check which activities have analyses
print("\n4. Checking which activities have analyses...")
activities_with_analysis = con.execute("""
    SELECT a.activity_id, a.athlete_id, 
           CASE WHEN ra.activity_id IS NOT NULL THEN 'YES' ELSE 'NO' END as has_analysis
    FROM activities a
    LEFT JOIN ride_analysis ra ON a.activity_id = ra.activity_id
    ORDER BY a.updated_at DESC
    LIMIT 10
""").fetchall()

for row in activities_with_analysis:
    print(f"   - Activity ID: {row['activity_id']}, Has Analysis: {row['has_analysis']}")

# Check webhook events
print("\n5. Checking recent webhook events...")
events = con.execute("""
    SELECT id, object_id, status, last_error, received_at
    FROM webhook_events
    ORDER BY received_at DESC
    LIMIT 10
""").fetchall()

print(f"   Found {len(events)} recent webhook events")
for row in events:
    error_info = f", Error: {row['last_error']}" if row['last_error'] else ""
    print(f"   - Event {row['id']}: Activity {row['object_id']}, Status: {row['status']}{error_info}")

print("\n" + "=" * 60)
print("Debug complete")
print("=" * 60)

