"""
OnCall Rehearsal Agent — Data Loader

Loads scenario data from data/scenarios/<scenario_id>/ files.
Scenario IDs are ALWAYS validated against ALLOWED_SCENARIOS allowlist.
No file path is ever constructed directly from user input.

Path traversal protection:
  - validate_scenario_id() rejects any ID not in the explicit allowlist
  - os.path.join is used with the allowlisted ID only
  - The constructed path is verified to be within the data/ directory
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from app.models import ALLOWED_SCENARIOS

# Absolute path to the data directory (resolved at import time)
_DATA_DIR = Path(__file__).parent.parent / "data"
_PAST_INCIDENTS_PATH = _DATA_DIR / "past_incidents.csv"


# ── Validation ─────────────────────────────────────────────────────────────

def validate_scenario_id(scenario_id: str) -> str:
    """
    Validate scenario_id against the explicit allowlist.
    Raises ValueError for any value not in ALLOWED_SCENARIOS.
    This is the ONLY place scenario_id validation should happen.
    """
    if scenario_id not in ALLOWED_SCENARIOS:
        raise ValueError(
            f"Invalid scenario_id. Allowed values: {sorted(ALLOWED_SCENARIOS)}"
        )
    return scenario_id


def _scenario_path(scenario_id: str) -> Path:
    """Return the validated absolute path to a scenario directory."""
    sid = validate_scenario_id(scenario_id)
    path = (_DATA_DIR / "scenarios" / sid).resolve()
    # Extra safety: confirm we're inside data/scenarios/
    if not str(path).startswith(str((_DATA_DIR / "scenarios").resolve())):
        raise ValueError("Path traversal detected")
    return path


def load_scenario_metadata(scenario_id: str) -> dict[str, Any]:
    """
    Load metadata for a scenario from data/scenarios/<scenario_id>/metadata.json.
    Falls back to sensible defaults if metadata.json is not present.
    """
    sid = validate_scenario_id(scenario_id)
    meta_path = _scenario_path(sid) / "metadata.json"
    if meta_path.exists():
        try:
            with open(meta_path, encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "id": sid,
                    "title": _sanitize_string(str(data.get("title", sid))),
                    "service_name": _sanitize_string(str(data.get("service_name", "Production Service"))),
                    "severity": _sanitize_string(str(data.get("severity", "SEV 2"))),
                }
        except Exception:
            pass

    # Default fallback
    formatted_title = sid.replace("_", " ").title()
    return {
        "id": sid,
        "title": formatted_title,
        "service_name": "Production Service",
        "severity": "SEV 2",
    }


def load_all_scenarios_metadata() -> list[dict[str, Any]]:
    """Return metadata for all allowlisted scenarios in sorted order."""
    return [load_scenario_metadata(sid) for sid in sorted(ALLOWED_SCENARIOS)]


def _sanitize_string(value: str) -> str:
    """
    Strip control characters and prompt-injection markers from string values.
    Tool output is wrapped in delimiters in the agent layer, but we also
    sanitize here as a defence-in-depth measure.
    """
    from app.sanitizer import detect_and_neutralize
    # Remove null bytes
    value = value.replace("\x00", "")
    # Strip ANSI escape codes
    value = re.sub(r"\x1b\[[0-9;]*m", "", value)
    # Neutralize script tags and prompt injection markers
    value, _ = detect_and_neutralize(value)
    return value


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize string values in a dict."""
    return {
        k: _sanitize_string(v) if isinstance(v, str) else v
        for k, v in row.items()
    }


def _read_csv(path: Path) -> list[dict[str, Any]]:
    """Read a CSV file into a list of dicts with sanitized values."""
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [_sanitize_row(dict(row)) for row in reader]


# ── Data Loaders ───────────────────────────────────────────────────────────

def load_logs(
    scenario_id: str,
    minutes: Optional[int] = None,
    level: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Load logs for a scenario with optional filtering.

    Args:
        scenario_id: validated against ALLOWED_SCENARIOS
        minutes: if set, only return logs from the last N minutes
        level: filter by log level (INFO, WARNING, ERROR, CRITICAL, DEBUG)
        keyword: case-insensitive keyword filter on message
    """
    path = _scenario_path(scenario_id) / "logs.csv"
    rows = _read_csv(path)

    if level:
        level_upper = level.upper()
        rows = [r for r in rows if r.get("level", "").upper() == level_upper]

    if keyword:
        kw_lower = keyword.lower()
        rows = [r for r in rows if kw_lower in r.get("message", "").lower()]

    # minutes filtering: relative to latest simulated timestamp in the dataset
    if minutes is not None and rows:
        from datetime import datetime, timedelta, timezone
        parsed_times = []
        for r in rows:
            ts_str = r.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                parsed_times.append(dt)
            except ValueError:
                pass
        ref_time = max(parsed_times) if parsed_times else datetime.now(timezone.utc)
        cutoff = ref_time - timedelta(minutes=minutes)
        filtered = []
        for row in rows:
            ts_str = row.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    filtered.append(row)
            except ValueError:
                filtered.append(row)  # Keep rows with unparseable timestamps
        rows = filtered

    return rows


def load_metrics(
    scenario_id: str,
    metric: Optional[str] = None,
    minutes: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Load metrics for a scenario.

    Args:
        metric: if set, only return this column plus timestamp
        minutes: if set, only return metrics from the last N minutes
    """
    path = _scenario_path(scenario_id) / "metrics.csv"
    raw_rows = _read_csv(path)

    # Cast numeric metric columns
    rows = []
    numeric_cols = {"p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"}
    for r in raw_rows:
        parsed_row: dict[str, Any] = {}
        for k, v in r.items():
            if k in numeric_cols and isinstance(v, str):
                try:
                    parsed_row[k] = float(v) if "." in v else int(v)
                except ValueError:
                    parsed_row[k] = v
            else:
                parsed_row[k] = v
        rows.append(parsed_row)

    if minutes is not None and rows:
        from datetime import datetime, timedelta, timezone
        parsed_times = []
        for r in rows:
            ts_str = r.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                parsed_times.append(dt)
            except ValueError:
                pass
        ref_time = max(parsed_times) if parsed_times else datetime.now(timezone.utc)
        cutoff = ref_time - timedelta(minutes=minutes)
        filtered = []
        for row in rows:
            ts_str = row.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    filtered.append(row)
            except ValueError:
                filtered.append(row)
        rows = filtered

    if metric:
        # Return only the requested metric + timestamp
        allowed_metrics = {
            "p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"
        }
        if metric in allowed_metrics:
            rows = [
                {"timestamp": r.get("timestamp"), metric: r.get(metric)}
                for r in rows
            ]
        # else: return all columns (don't expose error message about metric names)

    return rows


def load_deploys(
    scenario_id: str,
    hours: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Load deploy records for a scenario.

    Args:
        hours: if set, only return deploys from the last N hours
    """
    path = _scenario_path(scenario_id) / "deploys.csv"
    rows = _read_csv(path)

    if hours is not None and rows:
        from datetime import datetime, timedelta, timezone
        parsed_times = []
        for r in rows:
            ts_str = r.get("time", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                parsed_times.append(dt)
            except ValueError:
                pass
        ref_time = max(parsed_times) if parsed_times else datetime.now(timezone.utc)
        cutoff = ref_time - timedelta(hours=hours)
        filtered = []
        for row in rows:
            ts_str = row.get("time", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    filtered.append(row)
            except ValueError:
                filtered.append(row)
        rows = filtered

    return rows


def load_sandbox_effects(scenario_id: str) -> dict[str, Any]:
    """Load sandbox simulation effects for a scenario."""
    path = _scenario_path(scenario_id) / "sandbox_effects.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Sanitize string values
    sanitized: dict[str, Any] = {}
    for fix_id, effect in data.items():
        if isinstance(effect, dict):
            sanitized[fix_id] = {
                k: _sanitize_string(v) if isinstance(v, str) else v
                for k, v in effect.items()
            }
        else:
            sanitized[fix_id] = effect
    return sanitized


def search_past_incidents(query: str) -> list[dict[str, Any]]:
    """
    Simple keyword-score search over past_incidents.csv AND team incident memory.

    Saved records are tagged 'from your team' and formatted as passive untrusted observations.
    Returns up to 5 most relevant incidents, scored by keyword overlap.
    """
    query_tokens = set(query.lower().split()) if query else set()

    scored: list[tuple[int, dict[str, Any]]] = []

    # 1. Search static past_incidents.csv
    if _PAST_INCIDENTS_PATH.exists():
        rows = _read_csv(_PAST_INCIDENTS_PATH)
        for row in rows:
            text = " ".join([
                row.get("symptoms", ""),
                row.get("root_cause", ""),
                row.get("fix", ""),
            ]).lower()
            score = sum(1 for token in query_tokens if token in text) if query_tokens else 1
            if score > 0 or not query_tokens:
                scored.append((score, row))

    # 2. Search saved team incident memories (Phase 12)
    try:
        from app import database as db
        memories = db.list_incident_memories(limit=100)
        for mem in memories:
            row_dict = dict(mem)
            cause = _sanitize_string(str(row_dict.get("cause", "")))
            fix = _sanitize_string(str(row_dict.get("fix", "")))
            outcome = _sanitize_string(str(row_dict.get("outcome", "")))
            scenario_id = _sanitize_string(str(row_dict.get("scenario_id", "")))
            username = _sanitize_string(str(row_dict.get("username", "teammate")))

            text = f"{scenario_id} {cause} {fix} {outcome}".lower()
            score = sum(1 for token in query_tokens if token in text) if query_tokens else 1
            if score > 0 or not query_tokens:
                item = {
                    "incident_id": f"MEM-{row_dict.get('id')}",
                    "title": f"Incident {scenario_id} ({outcome})",
                    "symptoms": cause,
                    "root_cause": cause,
                    "fix": fix,
                    "outcome": outcome,
                    "source": "from your team",
                    "recorded_by": username,
                    "timestamp": str(row_dict.get("timestamp", "")),
                }
                # Boost team memory slightly so relevant teammate experience surfaces
                scored.append((score + 1, item))
    except Exception:
        pass  # DB might not be initialized in isolation tests

    # Sort descending by score, return top 5
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:5]]
