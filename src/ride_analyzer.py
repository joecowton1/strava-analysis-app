"""
AI-powered ride analysis module.

Analyzes Strava activities and generates insights using OpenAI's API.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import get_settings

# Prompt version - extracted from prompt file
_PROMPT_VERSION = "fred_v3"

def _extract_model_from_prompt(template: str) -> str | None:
    """
    Parse a line like: MODEL=gpt-5.2
    Returns None if not present.
    """
    for line in template.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.upper().startswith("MODEL="):
            v = s.split("=", 1)[1].strip()
            return v or None
    return None

def _load_prompt_template() -> str:
    """Load the prompt template from file. Always reloads from disk (no caching)."""
    prompt_path = Path(__file__).parent / "prompts" / "prompt_v1.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}. Please create src/prompts/prompt_v1.md")
    
    template = prompt_path.read_text()
    if not template.strip():
        raise ValueError(f"Prompt file is empty: {prompt_path}")
    
    # Always reload from file (no caching) to ensure latest version is always used
    return template


def analyze_ride(activity_data: Dict[str, Any], streams_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Analyze a ride using AI and return structured analysis.
    
    Args:
        activity_data: Activity data from Strava API
        streams_data: Optional streams data (power, heart rate, etc.)
    
    Returns:
        Dictionary with 'metrics' (structured data) and 'narrative' (markdown text)
    """
    if OpenAI is None:
        raise RuntimeError("OpenAI package not installed. Install with: pip install openai")
    
    s = get_settings()
    if not hasattr(s, 'openai_api_key') or not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured in .env file")
    
    client = OpenAI(api_key=s.openai_api_key)
    
    # Get prompt version from template
    prompt_version = _PROMPT_VERSION
    
    # Extract key metrics from activity
    name = activity_data.get("name", "Ride")
    distance_km = activity_data.get("distance", 0) / 1000
    moving_time_sec = activity_data.get("moving_time", 0)
    elapsed_time_sec = activity_data.get("elapsed_time", 0)
    elevation_gain = activity_data.get("total_elevation_gain", 0)
    avg_speed_kmh = activity_data.get("average_speed", 0) * 3.6
    max_speed_kmh = activity_data.get("max_speed", 0) * 3.6
    avg_watts = activity_data.get("average_watts")
    np_watts = activity_data.get("weighted_average_watts")
    max_watts = activity_data.get("max_watts")
    avg_heartrate = activity_data.get("average_heartrate")
    max_heartrate = activity_data.get("max_heartrate")
    avg_cadence = activity_data.get("average_cadence")
    sport_type = activity_data.get("sport_type", "Ride")
    start_date = activity_data.get("start_date", "")
    
    def _extract_stream(streams: Dict[str, Any] | None, key: str):
        if not streams or not isinstance(streams, dict):
            return None
        s = streams.get(key)
        if isinstance(s, dict):
            return s.get("data")
        return None

    def _compute_post_climb_power_w(streams: Dict[str, Any] | None) -> Dict[str, Any] | None:
        """
        Heuristic: detect climb ends from altitude trend changes, then compute average power
        in a short window after each climb end.
        Returns None if required streams aren't available.
        """
        alt = _extract_stream(streams, "altitude")
        watts = _extract_stream(streams, "watts")
        vel = _extract_stream(streams, "velocity_smooth")
        t = _extract_stream(streams, "time")
        if not (isinstance(alt, list) and isinstance(watts, list) and isinstance(vel, list) and isinstance(t, list)):
            return None
        n = min(len(alt), len(watts), len(vel), len(t))
        if n < 60:
            return None

        # Parameters (tuned for simplicity, not perfection)
        climb_window_sec = 60
        min_alt_gain_m = 6.0          # in window
        max_speed_mps = 6.0           # "climbing-ish"
        post_window_sec = 120         # post-climb window to average power
        min_moving_speed_mps = 1.0

        # Determine sample rate from time stream (seconds)
        dt = 1
        try:
            dt = max(1, int(round((t[min(10, n-1)] - t[0]) / max(1, min(10, n-1)))))
        except Exception:
            dt = 1
        w_steps = max(1, int(climb_window_sec / dt))
        post_steps = max(1, int(post_window_sec / dt))

        # Mark indices that are within a "climb-ish" window
        climbish = [False] * n
        for i in range(w_steps, n):
            try:
                gain = alt[i] - alt[i - w_steps]
                if gain >= min_alt_gain_m and vel[i] <= max_speed_mps:
                    climbish[i] = True
            except Exception:
                continue

        # Identify climb end indices: climbish -> not climbish transition
        ends = []
        for i in range(1, n):
            if climbish[i - 1] and not climbish[i]:
                ends.append(i)

        if not ends:
            return {"climb_count": 0, "post_climb_avg_w": None}

        post_avgs = []
        for end in ends:
            start = end
            stop = min(n, end + post_steps)
            vals = []
            for j in range(start, stop):
                try:
                    if vel[j] < min_moving_speed_mps:
                        continue
                    p = watts[j]
                    # Ignore zeros (coasting / stop) to better reflect "power floor when pedaling"
                    if p and p > 0:
                        vals.append(float(p))
                except Exception:
                    continue
            if vals:
                post_avgs.append(sum(vals) / len(vals))

        if not post_avgs:
            return {"climb_count": len(ends), "post_climb_avg_w": None}

        # Use median to reduce outlier influence
        post_avgs_sorted = sorted(post_avgs)
        mid = len(post_avgs_sorted) // 2
        median = post_avgs_sorted[mid] if len(post_avgs_sorted) % 2 == 1 else (post_avgs_sorted[mid - 1] + post_avgs_sorted[mid]) / 2
        return {"climb_count": len(ends), "post_climb_avg_w": median}
    
    # Build activity summary for the prompt
    ride_brief_parts = [
        f"- Name: {name}",
        f"- Distance: {distance_km:.2f} km",
        f"- Moving Time: {moving_time_sec // 60} minutes {moving_time_sec % 60} seconds",
        f"- Elevation Gain: {elevation_gain:.0f} m",
        f"- Average Speed: {avg_speed_kmh:.2f} km/h",
        f"- Max Speed: {max_speed_kmh:.2f} km/h",
    ]
    
    if avg_watts:
        ride_brief_parts.append(f"- Average Power: {avg_watts:.0f} W")
    if np_watts:
        ride_brief_parts.append(f"- Normalized Power (weighted_average_watts): {np_watts:.0f} W")
    if avg_watts and np_watts and avg_watts > 0:
        vi = float(np_watts) / float(avg_watts)
        ride_brief_parts.append(f"- VI (NP/Avg): {vi:.3f}")
    if max_watts:
        ride_brief_parts.append(f"- Max Power: {max_watts:.0f} W")
    if avg_heartrate:
        ride_brief_parts.append(f"- Average Heart Rate: {avg_heartrate:.0f} bpm")
        if max_heartrate:
            ride_brief_parts.append(f"- Max Heart Rate: {max_heartrate:.0f} bpm")
    if avg_cadence:
        ride_brief_parts.append(f"- Average Cadence: {avg_cadence:.0f} rpm")
    
    if streams_data:
        ride_brief_parts.append("\n- Stream data (time-series) is available for detailed analysis.")
        post = _compute_post_climb_power_w(streams_data)
        if post:
            if post.get("climb_count", 0) == 0:
                ride_brief_parts.append("- Post-climb power: not available (no climbs detected in streams)")
            else:
                pc = post.get("post_climb_avg_w")
                if pc is None:
                    ride_brief_parts.append(f"- Post-climb power (median 2-min avg after climbs): not available (climbs_detected={post.get('climb_count')})")
                else:
                    ride_brief_parts.append(f"- Post-climb power (median 2-min avg after climbs): {pc:.0f} W (climbs_detected={post.get('climb_count')})")
        else:
            ride_brief_parts.append("- Post-climb power: not available (missing required streams)")
    
    ride_brief = "\n".join(ride_brief_parts)
    
    # ALWAYS load prompt template from file and replace placeholder
    prompt_template = _load_prompt_template()
    model_override = _extract_model_from_prompt(prompt_template)
    model_used = model_override or s.openai_model
    
    # The placeholder may be multi-line, so use regex to find and replace it
    import re
    
    # Try multiple placeholder patterns (supports both old and new formats)
    placeholder_patterns = [
        r'\{paste JSON or bullet summary here\}',  # Old format (single line)
        r'\{Paste JSON, table, or bullet summary here[\s\S]*?\(e\.g\.[^)]+\)\}',  # New format (multi-line with example)
        r'\{Paste JSON[^}]*\}',  # Fallback: any {Paste JSON...} pattern
    ]
    
    prompt = prompt_template
    placeholder_found = False
    
    for pattern in placeholder_patterns:
        match = re.search(pattern, prompt_template, re.IGNORECASE | re.DOTALL)
        if match:
            prompt = prompt_template.replace(match.group(0), ride_brief)
            placeholder_found = True
            break
    
    if not placeholder_found:
        raise ValueError(f"Prompt template missing required placeholder. Expected pattern like '{{Paste JSON...}}' or '{{paste JSON or bullet summary here}}'")
    
    # Verify prompt contains expected content
    if "Fred Whitton" not in prompt and "ATHLETE PROFILE" not in prompt:
        print(f"⚠ Warning: Prompt may not be the expected Fred Whitton prompt. First 100 chars: {prompt[:100]}")
    
    # Check if prompt expects JSON format (old format) or markdown (new format)
    use_json_format = "JSON format" in prompt and "json_object" in prompt.lower()
    
    try:
        # ALWAYS use the prompt from file as user message - no system message, no fallback
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        create_kwargs = {
            "model": model_used,
            "messages": messages,
            "temperature": 0.7,
        }
        
        # Only use JSON format if explicitly requested in prompt
        if use_json_format:
            create_kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**create_kwargs)
            result = json.loads(response.choices[0].message.content)
            
            # Ensure we have the expected structure
            if "metrics" not in result:
                result["metrics"] = {}
            if "narrative" not in result:
                result["narrative"] = result.get("narrative", "No narrative generated.")
            
            return {
                "metrics": result["metrics"],
                "narrative": result["narrative"],
                "prompt_version": prompt_version,
                "model": model_used,
            }
        else:
            # Default: markdown response (for Fred Whitton prompt)
            response = client.chat.completions.create(**create_kwargs)
            narrative = response.choices[0].message.content
            
            # Store entire response as narrative, create minimal metrics structure
            return {
                "metrics": {
                    "prompt_version": prompt_version
                },
                "narrative": narrative,
                "prompt_version": prompt_version,
                "model": model_used,
            }
    
    except Exception as e:
        # Return a basic analysis if AI fails
        return {
            "metrics": {
                "error": str(e)
            },
            "narrative": f"## Analysis Error\n\nUnable to generate AI analysis: {str(e)}",
            "prompt_version": prompt_version,
            "model": model_used,
        }

