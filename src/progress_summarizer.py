"""
Progress summarizer.

After each ride is analyzed, we can optionally call OpenAI again to summarize progress
across all past ride reports in chronological order.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import get_settings

_PROMPT_VERSION = "progress_v1"

def _extract_model_from_prompt(template: str) -> str | None:
    for line in template.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.upper().startswith("MODEL="):
            v = s.split("=", 1)[1].strip()
            return v or None
    return None


def _load_prompt_template() -> str:
    prompt_path = Path(__file__).parent / "prompts" / "progress_summary_v1.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    template = prompt_path.read_text(encoding="utf-8")
    if not template.strip():
        raise ValueError(f"Prompt file is empty: {prompt_path}")
    return template


def _format_reports_chronological(analyses: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for a in analyses:
        act = a.get("activity") or {}
        name = act.get("name") or "Untitled Ride"
        start_date = act.get("start_date") or ""
        created_at = a.get("created_at") or 0
        created_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(created_at))) if created_at else ""

        header = f"### {start_date or created_str} — {name} (activity_id={a['activity_id']})"
        parts.append(header)
        parts.append("")
        parts.append(a.get("narrative") or "")
        parts.append("\n---\n")
    return "\n".join(parts).strip()


def summarize_progress(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarize progress across all ride analyses (chronological).

    Returns:
        { "summary_md": str, "prompt_version": str }
    """
    if OpenAI is None:
        raise RuntimeError("OpenAI package not installed. Install with: pip install openai")

    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    template = _load_prompt_template()
    model_override = _extract_model_from_prompt(template)
    model_used = model_override or s.openai_model
    model_override = _extract_model_from_prompt(template)
    placeholder = "{PASTE_REPORTS_HERE}"
    if placeholder not in template:
        raise ValueError(f"Progress summary prompt missing required placeholder {placeholder!r}")

    reports_text = _format_reports_chronological(analyses)
    if not reports_text.strip():
        raise ValueError("No reports available to summarize")

    # Prevent unbounded prompt growth
    max_chars = int(os.environ.get("PROGRESS_SUMMARY_MAX_CHARS", "60000"))
    if len(reports_text) > max_chars:
        # Keep most recent reports while preserving chronological order of what remains.
        trimmed = analyses[:]
        while trimmed and len(_format_reports_chronological(trimmed)) > max_chars:
            trimmed.pop(0)
        reports_text = _format_reports_chronological(trimmed)
        reports_text = (
            f"NOTE: Older reports were truncated due to size limits.\n\n{reports_text}"
        )

    prompt = template.replace(placeholder, reports_text)

    client = OpenAI(api_key=s.openai_api_key)
    resp = client.chat.completions.create(
        model=model_used,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    summary_md = resp.choices[0].message.content or ""
    return {"summary_md": summary_md, "prompt_version": _PROMPT_VERSION, "model": model_used}


