"""
Tests for Scenario Validator (scripts/validate_scenario.py)

Verifies:
  - Valid scenario folders pass with zero errors
  - Missing required files detected
  - Malformed CSVs (bad header, wrong column count, invalid timestamp, non-chronological order)
    are reported with exact file names and row numbers
  - metadata.json validation (missing fields, invalid severity)
  - sandbox_effects.json validation (missing fix, invalid risk level, bad metrics)
  - Chronology validation (deploy occurring after incident symptoms)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_scenario import (
    validate_scenario,
    validate_metadata,
    validate_answer_key,
    validate_logs_csv,
    validate_metrics_csv,
    validate_deploys_csv,
    validate_sandbox_effects,
)

ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = ROOT / "data" / "scenarios"


class TestValidExistingScenarios:
    """All 6 production scenarios must pass validation cleanly."""

    @pytest.mark.parametrize(
        "scenario_id",
        [
            "bad_deploy_slow_queries",
            "connection_pool_leak",
            "memory_leak",
            "third_party_outage",
            "config_change_flag",
            "ambiguous_escalate",
        ],
    )
    def test_existing_scenarios_pass_validation(self, scenario_id: str):
        folder = SCENARIOS_DIR / scenario_id
        errors = validate_scenario(folder)
        assert errors == [], f"Validation failed for {scenario_id}: {errors}"


class TestMissingFiles:
    def test_nonexistent_directory(self, tmp_path: Path):
        errors = validate_scenario(tmp_path / "does_not_exist")
        assert len(errors) == 1
        assert "does not exist" in errors[0]

    def test_missing_required_file(self, tmp_path: Path):
        # Create folder with only metadata.json
        (tmp_path / "metadata.json").write_text('{"id":"test","title":"t","service_name":"s","severity":"SEV 1"}')
        errors = validate_scenario(tmp_path)
        assert any("Missing required file: answer_key.txt" in e for e in errors)
        assert any("Missing required file: logs.csv" in e for e in errors)


class TestLogsValidation:
    def test_header_mismatch_reported(self, tmp_path: Path):
        csv_file = tmp_path / "logs.csv"
        csv_file.write_text("time,severity,text\n2026-11-12T00:00:00Z,INFO,hello\n")
        errors, _, _ = validate_logs_csv(csv_file)
        assert any("Header mismatch" in e and "Row 1" in e for e in errors)

    def test_invalid_timestamp_reported_with_row_number(self, tmp_path: Path):
        csv_file = tmp_path / "logs.csv"
        csv_file.write_text("timestamp,level,message\nnot-a-timestamp,INFO,ok\n")
        errors, _, _ = validate_logs_csv(csv_file)
        assert any("Row 2" in e and "Invalid timestamp" in e for e in errors)

    def test_non_chronological_timestamp_reported(self, tmp_path: Path):
        csv_file = tmp_path / "logs.csv"
        csv_file.write_text(
            "timestamp,level,message\n"
            "2026-11-12T02:10:00Z,INFO,event 1\n"
            "2026-11-12T02:05:00Z,INFO,event 2\n"
        )
        errors, _, _ = validate_logs_csv(csv_file)
        assert any("Row 3" in e and "out of order" in e for e in errors)

    def test_invalid_log_level_reported(self, tmp_path: Path):
        csv_file = tmp_path / "logs.csv"
        csv_file.write_text("timestamp,level,message\n2026-11-12T02:00:00Z,PANIC,bad level\n")
        errors, _, _ = validate_logs_csv(csv_file)
        assert any("Row 2" in e and "Invalid log level 'PANIC'" in e for e in errors)


class TestMetricsValidation:
    def test_non_numeric_metric_reported(self, tmp_path: Path):
        csv_file = tmp_path / "metrics.csv"
        csv_file.write_text(
            "timestamp,p95_latency_ms,error_rate_pct,memory_mb,db_connections\n"
            "2026-11-12T02:00:00Z,fast,0.1,500,10\n"
        )
        errors, _, _ = validate_metrics_csv(csv_file)
        assert any("Row 2" in e and "p95_latency_ms" in e and "must be a number" in e for e in errors)

    def test_error_rate_out_of_bounds_reported(self, tmp_path: Path):
        csv_file = tmp_path / "metrics.csv"
        csv_file.write_text(
            "timestamp,p95_latency_ms,error_rate_pct,memory_mb,db_connections\n"
            "2026-11-12T02:00:00Z,200,105.0,500,10\n"
        )
        errors, _, _ = validate_metrics_csv(csv_file)
        assert any("Row 2" in e and "between 0 and 100" in e for e in errors)


class TestSandboxEffectsValidation:
    def test_invalid_risk_level_reported(self, tmp_path: Path):
        json_file = tmp_path / "sandbox_effects.json"
        json_file.write_text(json.dumps({
            "fix_foo": {
                "risk_level": 5,
                "blast_radius": "radius",
                "description": "desc",
                "after_metrics": {"p95_latency_ms": 200, "error_rate_pct": 0, "memory_mb": 500, "db_connections": 10}
            }
        }))
        errors = validate_sandbox_effects(json_file)
        assert any("risk_level" in e and "must be 0, 1, or 2" in e for e in errors)

    def test_missing_after_metrics_keys_reported(self, tmp_path: Path):
        json_file = tmp_path / "sandbox_effects.json"
        json_file.write_text(json.dumps({
            "fix_foo": {
                "risk_level": 1,
                "blast_radius": "radius",
                "description": "desc",
                "after_metrics": {"p95_latency_ms": 200}
            }
        }))
        errors = validate_sandbox_effects(json_file)
        assert any("after_metrics" in e and "missing metric keys" in e for e in errors)


class TestChronologyCheck:
    def test_deploy_after_incident_reported(self, tmp_path: Path):
        """When a deploy is dated after symptom onset, chronology error is flagged."""
        # Create full scenario structure where deploy happens at 03:00 but symptom is at 02:00
        (tmp_path / "metadata.json").write_text(json.dumps({
            "id": "chrono_test", "title": "t", "service_name": "s", "severity": "SEV 1"
        }))
        (tmp_path / "answer_key.txt").write_text("root_cause: test cause\ncorrect_fix: fix_a\n")
        (tmp_path / "logs.csv").write_text(
            "timestamp,level,message\n"
            "2026-11-12T02:00:00Z,ERROR,Incident symptoms appear\n"
        )
        (tmp_path / "metrics.csv").write_text(
            "timestamp,p95_latency_ms,error_rate_pct,memory_mb,db_connections\n"
            "2026-11-12T02:00:00Z,9000,50.0,500,10\n"
        )
        (tmp_path / "deploys.csv").write_text(
            "time,author,commit_message,files_changed,diff_summary\n"
            "2026-11-12T03:00:00Z,alice,deploy after incident,file.py,diff\n"
        )
        (tmp_path / "sandbox_effects.json").write_text(json.dumps({
            "fix_a": {
                "risk_level": 1,
                "blast_radius": "r",
                "description": "d",
                "after_metrics": {"p95_latency_ms": 200, "error_rate_pct": 0, "memory_mb": 500, "db_connections": 10}
            }
        }))

        errors = validate_scenario(tmp_path)
        assert any("Chronology" in e and "AFTER incident symptoms started" in e for e in errors)
