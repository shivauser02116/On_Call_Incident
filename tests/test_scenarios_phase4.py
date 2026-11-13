"""
Phase 4 scenario tests: third_party_outage, config_change_flag, ambiguous_escalate.

Verifies:
- Data loads correctly (logs, metrics, deploys, sandbox_effects, metadata)
- Log formats are correct (Java, Node.js, Python tracebacks respectively)
- Red-herring and low-confidence signals are present in the data
- Fix IDs and risk levels are correct
- New INC-021..023 entries are in past_incidents.csv
"""

import json
import csv
from pathlib import Path

import pytest

from app.data_loader import (
    load_logs,
    load_metrics,
    load_deploys,
    load_sandbox_effects,
)

SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"
INCIDENTS_CSV = Path(__file__).parent.parent / "data" / "past_incidents.csv"


# ---------------------------------------------------------------------------
# third_party_outage
# ---------------------------------------------------------------------------

class TestThirdPartyOutage:
    SID = "third_party_outage"

    def test_logs_load_non_empty(self):
        rows = load_logs(self.SID)
        assert len(rows) >= 100

    def test_logs_contain_java_stacktrace(self):
        rows = load_logs(self.SID)
        java_lines = [r for r in rows if "java.net.SocketTimeoutException" in r.get("message", "")]
        assert len(java_lines) >= 1, "Expected at least one Java stack trace"

    def test_logs_show_retry_storm(self):
        rows = load_logs(self.SID)
        storm_lines = [r for r in rows if "retry storm" in r.get("message", "").lower()
                       or "worker threads blocked" in r.get("message", "").lower()]
        assert len(storm_lines) >= 1

    def test_logs_contain_red_herring_deploy(self):
        """The promo banner deploy should appear in logs as a red herring."""
        rows = load_logs(self.SID)
        redherring = [
            r for r in rows
            if "promo" in r.get("message", "").lower()
            or "banner" in r.get("message", "").lower()
            or "deploy check" in r.get("message", "").lower()
        ]
        assert len(redherring) >= 1, "Red herring deploy entry must appear in logs"

    def test_metrics_load(self):
        rows = load_metrics(self.SID)
        assert len(rows) >= 10

    def test_deploys_contain_promo_redherring(self):
        rows = load_deploys(self.SID)
        assert len(rows) >= 1
        messages = [r.get("commit_message", "").lower() for r in rows]
        promo = any("promo" in m or "banner" in m for m in messages)
        assert promo, "Deploys CSV must contain the red-herring promo deploy"

    def test_sandbox_effects_fix_ids(self):
        effects = load_sandbox_effects(self.SID)
        assert "fix_enable_circuit_breaker" in effects, "fix_enable_circuit_breaker must be present"
        assert "fix_rollback_promo_deploy" in effects, "fix_rollback_promo_deploy must be present"

    def test_sandbox_effects_risk_levels(self):
        effects = load_sandbox_effects(self.SID)
        # Circuit breaker is safe (L1); rollback of non-causal deploy is L2
        assert effects["fix_enable_circuit_breaker"]["risk_level"] in (0, 1)
        assert effects["fix_rollback_promo_deploy"]["risk_level"] in (1, 2)

    def test_metadata_json_exists_and_valid(self):
        meta = json.loads((SCENARIOS_DIR / self.SID / "metadata.json").read_text())
        assert meta["id"] == self.SID
        assert "title" in meta
        assert "service_name" in meta
        assert "severity" in meta

    def test_answer_key_not_empty(self):
        key = (SCENARIOS_DIR / self.SID / "answer_key.txt").read_text().strip()
        assert len(key) > 10

    def test_answer_key_argues_against_deploy(self):
        """The answer key must explicitly dismiss the promo deploy as the cause."""
        key = (SCENARIOS_DIR / self.SID / "answer_key.txt").read_text().lower()
        assert any(w in key for w in ("promo", "banner", "red herring", "not the cause", "deploy is not"))


# ---------------------------------------------------------------------------
# config_change_flag
# ---------------------------------------------------------------------------

class TestConfigChangeFlag:
    SID = "config_change_flag"

    def test_logs_load_non_empty(self):
        rows = load_logs(self.SID)
        assert len(rows) >= 100

    def test_logs_contain_nodejs_stacktrace(self):
        rows = load_logs(self.SID)
        node_lines = [r for r in rows if "knex" in r.get("message", "").lower()
                      or "node_modules" in r.get("message", "")]
        assert len(node_lines) >= 1, "Expected at least one Node.js / Knex stack trace"

    def test_logs_contain_config_change_event(self):
        rows = load_logs(self.SID)
        config_lines = [
            r for r in rows
            if "db_pool_timeout_ms" in r.get("message", "")
            or "dynamicconfigwatcher" in r.get("message", "").lower()
        ]
        assert len(config_lines) >= 1, "Expected log line documenting the config change"

    def test_logs_no_code_deploy(self):
        """Logs must confirm no code deploy happened."""
        rows = load_logs(self.SID)
        no_deploy_lines = [
            r for r in rows
            if "no git deployments" in r.get("message", "").lower()
            or "no container image" in r.get("message", "").lower()
            or "deploymentaudit" in r.get("message", "").lower()
        ]
        assert len(no_deploy_lines) >= 1

    def test_metrics_load(self):
        rows = load_metrics(self.SID)
        assert len(rows) >= 10

    def test_deploys_csv_no_code_deploys(self):
        """The deploys CSV must be empty (no code deploys), or entries marked config-only."""
        rows = load_deploys(self.SID)
        # Either empty OR all entries are config changes, not code deploys
        code_deploys = [
            r for r in rows
            if r.get("type", "config") not in ("config", "config_change")
        ]
        assert len(code_deploys) == 0, "config_change_flag must have no code deploys"

    def test_sandbox_effects_fix_ids(self):
        effects = load_sandbox_effects(self.SID)
        assert "fix_revert_config_flag" in effects
        assert "fix_restart_node_cluster" in effects

    def test_sandbox_effects_risk_levels(self):
        effects = load_sandbox_effects(self.SID)
        assert effects["fix_revert_config_flag"]["risk_level"] == 0  # Safe: revert config
        assert effects["fix_restart_node_cluster"]["risk_level"] in (0, 1)

    def test_metadata_json_valid(self):
        meta = json.loads((SCENARIOS_DIR / self.SID / "metadata.json").read_text())
        assert meta["id"] == self.SID
        assert "title" in meta

    def test_answer_key_identifies_config(self):
        key = (SCENARIOS_DIR / self.SID / "answer_key.txt").read_text().lower()
        assert "db_pool_timeout_ms" in key or "config" in key


# ---------------------------------------------------------------------------
# ambiguous_escalate
# ---------------------------------------------------------------------------

class TestAmbiguousEscalate:
    SID = "ambiguous_escalate"

    def test_logs_load_non_empty(self):
        rows = load_logs(self.SID)
        assert len(rows) >= 100

    def test_logs_contain_python_traceback(self):
        rows = load_logs(self.SID)
        py_lines = [r for r in rows if "Traceback (most recent call last)" in r.get("message", "")]
        assert len(py_lines) >= 1, "Expected at least one Python traceback"

    def test_logs_contain_conflicting_signals(self):
        """Both TCP RST and DNS failures must appear, creating ambiguity."""
        rows = load_logs(self.SID)
        tcp_rst = any("rst" in r.get("message", "").lower() for r in rows)
        dns_fail = any("gaierror" in r.get("message", "").lower()
                       or "name resolution" in r.get("message", "").lower() for r in rows)
        assert tcp_rst, "Expected TCP RST signals in logs"
        assert dns_fail, "Expected DNS failure signals in logs"

    def test_metrics_load(self):
        rows = load_metrics(self.SID)
        assert len(rows) >= 10

    def test_sandbox_effects_all_read_only(self):
        """All fixes must be read-only (risk_level == 0)."""
        effects = load_sandbox_effects(self.SID)
        for fix_id, effect in effects.items():
            assert effect["risk_level"] == 0, (
                f"{fix_id} must be risk_level 0 (read-only) in ambiguous_escalate scenario"
            )

    def test_sandbox_effects_includes_human_escalation(self):
        effects = load_sandbox_effects(self.SID)
        assert "fix_escalate_human_operator" in effects

    def test_metadata_json_valid(self):
        meta = json.loads((SCENARIOS_DIR / self.SID / "metadata.json").read_text())
        assert meta["id"] == self.SID
        assert "title" in meta

    def test_answer_key_recommends_human(self):
        key = (SCENARIOS_DIR / self.SID / "answer_key.txt").read_text().lower()
        assert any(w in key for w in ("human", "escalate", "operator"))

    def test_answer_key_low_confidence(self):
        key = (SCENARIOS_DIR / self.SID / "answer_key.txt").read_text().lower()
        assert "low confidence" in key or "confidence" in key


# ---------------------------------------------------------------------------
# past_incidents.csv coverage
# ---------------------------------------------------------------------------

class TestPastIncidentsPhase4:
    def test_inc021_022_023_present(self):
        with open(INCIDENTS_CSV, newline="") as f:
            reader = csv.DictReader(f)
            incident_ids = [row.get("incident_id", row.get("id", "")) for row in reader]
        assert "INC-021" in incident_ids, "INC-021 (third_party_outage) must be in past_incidents.csv"
        assert "INC-022" in incident_ids, "INC-022 (config_change_flag) must be in past_incidents.csv"
        assert "INC-023" in incident_ids, "INC-023 (ambiguous_escalate) must be in past_incidents.csv"

    def test_inc021_related_to_payment(self):
        with open(INCIDENTS_CSV, newline="") as f:
            reader = csv.DictReader(f)
            rows = {row.get("incident_id", row.get("id", "")): row for row in reader}
        inc = rows.get("INC-021", {})
        combined = " ".join(inc.values()).lower()
        assert any(w in combined for w in ("payment", "payflow", "circuit breaker", "timeout"))

    def test_inc022_related_to_config(self):
        with open(INCIDENTS_CSV, newline="") as f:
            reader = csv.DictReader(f)
            rows = {row.get("incident_id", row.get("id", "")): row for row in reader}
        inc = rows.get("INC-022", {})
        combined = " ".join(inc.values()).lower()
        assert any(w in combined for w in ("config", "pool", "timeout", "db_pool"))

    def test_inc023_related_to_network(self):
        with open(INCIDENTS_CSV, newline="") as f:
            reader = csv.DictReader(f)
            rows = {row.get("incident_id", row.get("id", "")): row for row in reader}
        inc = rows.get("INC-023", {})
        combined = " ".join(inc.values()).lower()
        assert any(w in combined for w in ("network", "dns", "tcp", "escalat", "ambiguous"))
