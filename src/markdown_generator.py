"""
Markdown report generation module for ride analysis reports.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def generate_ride_markdown(
    activity_data: Dict[str, Any],
    analysis_data: Dict[str, Any],
    output_path: str,
) -> str:
    """
    Generate a markdown report for a ride analysis.

    Args:
        activity_data: Activity data from Strava API
        analysis_data: Dictionary with 'metrics' and 'narrative'
        output_path: Path where markdown should be saved

    Returns:
        Path to the generated markdown file
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ride_name = activity_data.get("name", "Untitled Ride")
    sport_type = activity_data.get("sport_type", "")
    distance_km = (activity_data.get("distance") or 0) / 1000
    moving_time_sec = activity_data.get("moving_time") or 0
    elevation_gain = activity_data.get("total_elevation_gain") or 0
    start_date = activity_data.get("start_date") or ""

    date_line = ""
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            date_line = dt.isoformat()
        except Exception:
            date_line = start_date

    metrics = analysis_data.get("metrics", {}) or {}
    narrative = analysis_data.get("narrative", "") or ""

    header_lines = [
        f"# {ride_name}",
        "",
        "## Ride Details",
        f"- **sport_type**: {sport_type}",
        f"- **distance_km**: {distance_km:.2f}",
        f"- **moving_time_sec**: {moving_time_sec}",
        f"- **elevation_gain_m**: {elevation_gain}",
    ]
    if date_line:
        header_lines.append(f"- **start_date**: {date_line}")

    md = "\n".join(header_lines)
    md += "\n\n## Analysis Metrics\n\n"
    md += "```json\n"
    md += json.dumps(metrics, indent=2, sort_keys=True)
    md += "\n```\n"

    md += "\n## Narrative\n\n"
    md += narrative.strip()
    md += "\n"

    out.write_text(md, encoding="utf-8")
    return str(out)


