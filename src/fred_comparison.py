"""
Fred Whitton build-up comparison generator.
Analyzes Jan-May riding patterns across multiple years.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .openai_client import ask_openai


def _load_prompt() -> dict[str, Any]:
    """Load the Fred comparison prompt template."""
    here = Path(__file__).parent
    prompt_path = here / "prompts" / "fred_comparison_v1.md"
    content = prompt_path.read_text(encoding="utf-8")
    
    # Extract metadata
    lines = content.strip().split("\n")
    model = "gpt-4o"
    prompt_version = "fred_comparison_v1"
    
    for line in lines:
        if line.startswith("MODEL="):
            model = line.split("=", 1)[1].strip()
        elif line.startswith("PROMPT_VERSION="):
            prompt_version = line.split("=", 1)[1].strip()
    
    # Remove metadata lines
    prompt_text = "\n".join(
        ln for ln in lines 
        if not ln.startswith(("MODEL=", "PROMPT_VERSION="))
    ).strip()
    
    return {
        "prompt": prompt_text,
        "model": model,
        "prompt_version": prompt_version,
    }


def _format_year_data(rides: list[dict[str, Any]]) -> str:
    """Format ride data grouped by year and month (Jan-May only)."""
    from collections import defaultdict
    
    # Group by year and month
    buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
    
    for ride in rides:
        start_date = ride.get("start_date")
        if not start_date:
            continue
        
        try:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            year = dt.year
            month = dt.month
            
            if 1 <= month <= 5:  # Jan-May only
                buckets[(year, month)].append(ride)
        except (ValueError, AttributeError):
            continue
    
    if not buckets:
        return "No ride data available for January-May period."
    
    # Sort years
    years = sorted(set(y for y, m in buckets.keys()))
    months = ["Jan", "Feb", "Mar", "Apr", "May"]
    
    output = []
    output.append("# Fred Whitton Build-up Data (January - May)\n")
    
    for year in years:
        output.append(f"\n## {year}\n")
        
        for month_num, month_name in enumerate(months, start=1):
            group = buckets.get((year, month_num), [])
            
            if not group:
                output.append(f"### {month_name}: No rides")
                continue
            
            # Aggregate metrics
            total_dist = sum(r.get("distance", 0) for r in group) / 1000  # km
            total_elev = sum(r.get("total_elevation_gain", 0) for r in group)  # m
            total_time = sum(r.get("moving_time", 0) for r in group) / 3600  # hrs
            ride_count = len(group)
            
            # Average power and HR (only for rides that have them)
            power_rides = [r for r in group if r.get("average_watts")]
            hr_rides = [r for r in group if r.get("average_heartrate")]
            
            avg_power = (
                sum(r["average_watts"] for r in power_rides) / len(power_rides)
                if power_rides else None
            )
            avg_hr = (
                sum(r["average_heartrate"] for r in hr_rides) / len(hr_rides)
                if hr_rides else None
            )
            
            output.append(f"### {month_name}")
            output.append(f"- **Rides**: {ride_count}")
            output.append(f"- **Distance**: {total_dist:.1f} km")
            output.append(f"- **Elevation**: {int(total_elev)} m")
            output.append(f"- **Time**: {total_time:.1f} hrs")
            if avg_power:
                output.append(f"- **Avg Power**: {int(avg_power)} W")
            if avg_hr:
                output.append(f"- **Avg HR**: {int(avg_hr)} bpm")
            output.append("")
    
    return "\n".join(output)


def generate_fred_comparison(rides: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Generate a Fred Whitton build-up comparison from ride data.
    
    Args:
        rides: List of ride dicts with fields like start_date, distance, 
               total_elevation_gain, moving_time, average_watts, average_heartrate
    
    Returns:
        Dict with keys: summary_md, model, prompt_version
    """
    meta = _load_prompt()
    formatted_data = _format_year_data(rides)
    
    user_message = f"{meta['prompt']}\n\n---\n\n{formatted_data}"
    
    try:
        response = ask_openai(
            system="You are a cycling coach specializing in long-distance climbing events.",
            user=user_message,
            model=meta["model"],
        )
        
        return {
            "summary_md": response,
            "model": meta["model"],
            "prompt_version": meta["prompt_version"],
        }
    except Exception as e:
        return {
            "summary_md": f"**Error generating comparison**: {e}",
            "model": meta["model"],
            "prompt_version": meta["prompt_version"],
        }
