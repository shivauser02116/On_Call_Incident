#!/usr/bin/env python3
"""
OnCall Rehearsal Agent — Scenario Data Validator

Validates scenario directories under data/scenarios/<scenario_id>/ to ensure:
  - All 6 required files exist
  - CSV headers, column types, and values are well-formed
  - Timestamps are valid ISO-8601 and strictly chronological
  - A deploy occurs before or around the onset of symptoms (when deploys exist)
  - sandbox_effects.json defines valid risk levels (0-2) and before/after metrics
  - answer_key.txt defines root_cause and correct_fix

Designed for non-developer teammates: prints clear, actionable errors
with exact file names and row numbers.

Usage:
    python scripts/validate_scenario.py data/scenarios/bad_deploy_slow_queries
    python scripts/validate_scenario.py data/scenarios/*
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"}
REQUIRED_FILES = [
    "metadata.json",
    "answer_key.txt",
    "deploys.csv",
    "logs.csv",
    "metrics.csv",
    "sandbox_effects.json",
]


def parse_iso_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO-8601 timestamp string into timezone-aware datetime."""
    if not ts_str or not isinstance(ts_str, str):
        return None
    cleaned = ts_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


ALLOWED_SEVERITIES = {
    "SEV 1",
    "SEV 2",
    "SEV 3",
    "SEV 4",
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
}


def validate_metadata(path: Path) -> list[str]:
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"[metadata.json] Invalid JSON format: {exc}"]

    if not isinstance(data, dict):
        return ["[metadata.json] Root of metadata.json must be a JSON object."]

    for field in ("id", "title", "service_name", "severity"):
        if field not in data or not str(data[field]).strip():
            errors.append(f"[metadata.json] Missing required field '{field}'.")

    sev = str(data.get("severity", "")).strip().upper()
    if sev and sev not in ALLOWED_SEVERITIES:
        errors.append(
            f"[metadata.json] 'severity' must be one of {', '.join(sorted(ALLOWED_SEVERITIES))}; got '{data.get('severity')}'."
        )

    return errors


def validate_answer_key(path: Path) -> list[str]:
    errors = []
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        return [f"[answer_key.txt] Could not read file: {exc}"]

    if len(text) < 20:
        errors.append("[answer_key.txt] File is empty or too short (must describe root cause and fix).")

    lower = text.lower()
    if "root_cause" not in lower:
        errors.append("[answer_key.txt] Missing 'root_cause:' section explaining the incident cause.")
    if "correct_fix" not in lower:
        errors.append("[answer_key.txt] Missing 'correct_fix:' section identifying the recommended remediation.")

    return errors


def validate_logs_csv(path: Path) -> Tuple[list[str], Optional[datetime], Optional[datetime]]:
    """Validate logs.csv. Returns (errors, first_timestamp, symptom_start_timestamp)."""
    errors: list[str] = []
    first_ts: Optional[datetime] = None
    symptom_ts: Optional[datetime] = None
    prev_ts: Optional[datetime] = None

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return (["[logs.csv] File is completely empty."], None, None)

            expected_header = ["timestamp", "level", "message"]
            if [h.strip() for h in header] != expected_header:
                errors.append(
                    f"[logs.csv: Row 1] Header mismatch. Expected '{','.join(expected_header)}', "
                    f"got '{','.join(header)}'."
                )

            for row_idx, row in enumerate(reader, start=2):
                if not row or all(not c.strip() for c in row):
                    continue
                if len(row) < 3:
                    errors.append(
                        f"[logs.csv: Row {row_idx}] Incomplete row: expected 3 columns (timestamp,level,message), got {len(row)}."
                    )
                    continue

                ts_str, level_str, msg_str = row[0].strip(), row[1].strip(), row[2].strip()

                ts = parse_iso_timestamp(ts_str)
                if ts is None:
                    errors.append(
                        f"[logs.csv: Row {row_idx}] Invalid timestamp format '{ts_str}'. Expected ISO-8601 (e.g. 2026-11-12T02:00:00Z)."
                    )
                else:
                    if first_ts is None:
                        first_ts = ts
                    if prev_ts and ts < prev_ts:
                        errors.append(
                            f"[logs.csv: Row {row_idx}] Timestamp '{ts_str}' is out of order (earlier than previous row timestamp)."
                        )
                    prev_ts = ts

                upper_level = level_str.upper()
                if upper_level not in ALLOWED_LOG_LEVELS:
                    errors.append(
                        f"[logs.csv: Row {row_idx}] Invalid log level '{level_str}'. Must be one of: {', '.join(sorted(ALLOWED_LOG_LEVELS))}."
                    )

                if upper_level in ("ERROR", "CRITICAL") and symptom_ts is None and ts is not None:
                    symptom_ts = ts

                if not msg_str:
                    errors.append(f"[logs.csv: Row {row_idx}] Log message cannot be empty.")

    except Exception as exc:
        errors.append(f"[logs.csv] Error parsing CSV: {exc}")

    return errors, first_ts, symptom_ts


def validate_metrics_csv(path: Path) -> Tuple[list[str], Optional[datetime], Optional[datetime]]:
    """Validate metrics.csv. Returns (errors, first_timestamp, symptom_start_timestamp)."""
    errors: list[str] = []
    first_ts: Optional[datetime] = None
    symptom_ts: Optional[datetime] = None
    prev_ts: Optional[datetime] = None

    expected_header = ["timestamp", "p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"]

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return (["[metrics.csv] File is completely empty."], None, None)

            if [h.strip() for h in header] != expected_header:
                errors.append(
                    f"[metrics.csv: Row 1] Header mismatch. Expected '{','.join(expected_header)}', "
                    f"got '{','.join(header)}'."
                )

            for row_idx, row in enumerate(reader, start=2):
                if not row or all(not c.strip() for c in row):
                    continue
                if len(row) < 5:
                    errors.append(
                        f"[metrics.csv: Row {row_idx}] Incomplete row: expected 5 columns, got {len(row)}."
                    )
                    continue

                ts_str = row[0].strip()
                ts = parse_iso_timestamp(ts_str)
                if ts is None:
                    errors.append(f"[metrics.csv: Row {row_idx}] Invalid timestamp format '{ts_str}'.")
                else:
                    if first_ts is None:
                        first_ts = ts
                    if prev_ts and ts < prev_ts:
                        errors.append(
                            f"[metrics.csv: Row {row_idx}] Timestamp '{ts_str}' is out of chronological order."
                        )
                    prev_ts = ts

                # Number checks
                try:
                    p95 = float(row[1].strip())
                    if p95 < 0:
                        errors.append(f"[metrics.csv: Row {row_idx}] 'p95_latency_ms' cannot be negative ({p95}).")
                except ValueError:
                    errors.append(f"[metrics.csv: Row {row_idx}] 'p95_latency_ms' must be a number, got '{row[1]}'.")

                try:
                    err_rate = float(row[2].strip())
                    if not (0.0 <= err_rate <= 100.0):
                        errors.append(
                            f"[metrics.csv: Row {row_idx}] 'error_rate_pct' must be between 0 and 100, got {err_rate}."
                        )
                    elif err_rate > 2.0 and symptom_ts is None and ts is not None:
                        symptom_ts = ts
                except ValueError:
                    errors.append(f"[metrics.csv: Row {row_idx}] 'error_rate_pct' must be a number, got '{row[2]}'.")

                try:
                    mem = float(row[3].strip())
                    if mem <= 0:
                        errors.append(f"[metrics.csv: Row {row_idx}] 'memory_mb' must be > 0, got {mem}.")
                except ValueError:
                    errors.append(f"[metrics.csv: Row {row_idx}] 'memory_mb' must be a number, got '{row[3]}'.")

                try:
                    conns = int(row[4].strip())
                    if conns < 0:
                        errors.append(f"[metrics.csv: Row {row_idx}] 'db_connections' cannot be negative, got {conns}.")
                except ValueError:
                    errors.append(f"[metrics.csv: Row {row_idx}] 'db_connections' must be an integer, got '{row[4]}'.")

    except Exception as exc:
        errors.append(f"[metrics.csv] Error parsing CSV: {exc}")

    return errors, first_ts, symptom_ts


def validate_deploys_csv(path: Path) -> Tuple[list[str], list[datetime]]:
    """Validate deploys.csv. Returns (errors, list_of_deploy_timestamps)."""
    errors: list[str] = []
    deploy_timestamps: list[datetime] = []
    expected_cols = {"time", "author", "commit_message", "files_changed", "diff_summary"}

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return (["[deploys.csv] File is empty."], [])

            fieldnames = {fn.strip() for fn in reader.fieldnames if fn}
            missing = expected_cols - fieldnames
            if missing:
                errors.append(f"[deploys.csv: Row 1] Missing required columns: {', '.join(sorted(missing))}.")

            for row_idx, row in enumerate(reader, start=2):
                if not row or all(not (v or "").strip() for v in row.values()):
                    continue

                t_str = (row.get("time") or "").strip()
                t = parse_iso_timestamp(t_str)
                if t is None:
                    errors.append(f"[deploys.csv: Row {row_idx}] Invalid timestamp in 'time' column: '{t_str}'.")
                else:
                    deploy_timestamps.append(t)

                for col in ("author", "commit_message", "files_changed", "diff_summary"):
                    if not (row.get(col) or "").strip():
                        errors.append(f"[deploys.csv: Row {row_idx}] Column '{col}' cannot be empty.")

    except Exception as exc:
        errors.append(f"[deploys.csv] Error reading CSV: {exc}")

    return errors, deploy_timestamps


def validate_sandbox_effects(path: Path) -> list[str]:
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"[sandbox_effects.json] Invalid JSON format: {exc}"]

    if not isinstance(data, dict):
        return ["[sandbox_effects.json] Root must be a JSON object mapping fix IDs to effect objects."]

    if not data:
        errors.append("[sandbox_effects.json] Must define at least one fix effect.")

    metric_keys = {"p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"}

    for fix_id, effect in data.items():
        prefix = f"[sandbox_effects.json: fix '{fix_id}']"
        if not isinstance(effect, dict):
            errors.append(f"{prefix} Value must be a JSON object.")
            continue

        risk = effect.get("risk_level")
        if risk not in (0, 1, 2):
            errors.append(f"{prefix} 'risk_level' must be 0, 1, or 2 (got {risk}).")

        blast = effect.get("blast_radius")
        if not isinstance(blast, str) or not blast.strip():
            errors.append(f"{prefix} Missing or empty required field 'blast_radius'.")

        desc = effect.get("description") or effect.get("rationale")
        if not isinstance(desc, str) or not desc.strip():
            errors.append(f"{prefix} Missing required field 'description' (or 'rationale').")

        # after_metrics is required
        after_m = effect.get("after_metrics")
        if not isinstance(after_m, dict):
            errors.append(f"{prefix} 'after_metrics' must be an object with metrics.")
        else:
            missing_metrics = metric_keys - set(after_m.keys())
            if missing_metrics:
                errors.append(
                    f"{prefix} 'after_metrics' is missing metric keys: {', '.join(sorted(missing_metrics))}."
                )
            for k, v in after_m.items():
                if not isinstance(v, (int, float)):
                    errors.append(f"{prefix} 'after_metrics.{k}' must be a numeric value, got '{v}'.")

        # before_metrics is optional, but if present must be valid
        if "before_metrics" in effect:
            before_m = effect["before_metrics"]
            if not isinstance(before_m, dict):
                errors.append(f"{prefix} 'before_metrics' must be an object with metrics.")
            else:
                for k, v in before_m.items():
                    if not isinstance(v, (int, float)):
                        errors.append(f"{prefix} 'before_metrics.{k}' must be a numeric value, got '{v}'.")

    return errors


def validate_scenario(folder_path: str | Path) -> list[str]:
    """
    Validate a scenario folder.
    Returns a list of human-readable error messages (empty list if scenario is valid).
    """
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return [f"Scenario folder does not exist: {folder}"]

    errors: list[str] = []

    # 1. Check all required files exist
    for filename in REQUIRED_FILES:
        filepath = folder / filename
        if not filepath.exists() or not filepath.is_file():
            errors.append(f"Missing required file: {filename}")

    if errors:
        return errors  # Halt early if foundational files are missing

    # 2. Validate metadata.json
    errors.extend(validate_metadata(folder / "metadata.json"))

    # 3. Validate answer_key.txt
    errors.extend(validate_answer_key(folder / "answer_key.txt"))

    # 4. Validate logs.csv
    log_errs, log_first_ts, log_symptom_ts = validate_logs_csv(folder / "logs.csv")
    errors.extend(log_errs)

    # 5. Validate metrics.csv
    metric_errs, metric_first_ts, metric_symptom_ts = validate_metrics_csv(folder / "metrics.csv")
    errors.extend(metric_errs)

    # 6. Validate deploys.csv
    deploy_errs, deploy_timestamps = validate_deploys_csv(folder / "deploys.csv")
    errors.extend(deploy_errs)

    # 7. Validate sandbox_effects.json
    errors.extend(validate_sandbox_effects(folder / "sandbox_effects.json"))

    # 8. Chronology check: If deploys exist, ensure at least one deploy happens before symptoms start
    symptom_start = log_symptom_ts or metric_symptom_ts
    if deploy_timestamps and symptom_start:
        earliest_deploy = min(deploy_timestamps)
        # Allow deploy within 15 minutes of symptom onset (or before it)
        if earliest_deploy > symptom_start:
            errors.append(
                f"[Chronology] Earliest deploy ({earliest_deploy.isoformat()}) occurred AFTER incident "
                f"symptoms started ({symptom_start.isoformat()}). In a causal scenario, the deploy must "
                "precede or coincide with the symptom onset."
            )

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_scenario.py <path_to_scenario_folder> [...]")
        print("Example: python scripts/validate_scenario.py data/scenarios/bad_deploy_slow_queries")
        return 1

    total_checked = 0
    total_failed = 0

    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_dir():
            continue

        # Skip template directory unless explicitly targeted
        if p.name.startswith("_") and len(sys.argv) > 2:
            continue

        total_checked += 1
        print(f"\n🔍 Validating scenario: {p.name} ({p})")
        errors = validate_scenario(p)

        if not errors:
            print(f"  ✅ PASS: All files, schemas, and timestamps are valid.")
        else:
            total_failed += 1
            print(f"  ❌ FAILED: Found {len(errors)} issue(s):")
            for err in errors:
                print(f"     • {err}")

    print("\n" + "=" * 60)
    print(f"Validation summary: {total_checked - total_failed}/{total_checked} scenarios valid.")
    print("=" * 60)

    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
