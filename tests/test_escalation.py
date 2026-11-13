"""
Phase 10 — Escalation Path Tests

Verifies:
  - POST /api/investigations/{id}/approve with action="escalate" returns 200
    and status "escalated", writes an audit entry "fix_escalated".
  - Escalation available for ambiguous_escalate scenario (confidence < 50%).
  - Escalation requires auth and CSRF (same as approve/reject).
  - Escalation with invalid investigation_id returns 404.
  - Escalation on already-decided investigation returns 400.
  - The ambiguous_escalate mock agent result has top confidence < 50%.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app import database as db
from tests.conftest import get_csrf_cookie, login


def _create_escalate_investigation(user_id: int) -> int:
    """Seed an investigation for the ambiguous_escalate scenario ready for decision."""
    inv_id = db.create_investigation(user_id=user_id, scenario_id="ambiguous_escalate")
    result = {
        "hypotheses": [
            {
                "rank": 1,
                "cause": "Intermittent TCP reset packets — transit gateway packet loss.",
                "confidence": 0.38,
                "evidence_for": [{"description": "ConnectionResetError in logs", "tool_call": "query_logs", "source_row": "logs.csv:1"}],
                "evidence_against": [{"description": "Only 4.2% of requests fail", "tool_call": "get_metrics", "source_row": "metrics.csv:1"}],
            },
            {
                "rank": 2,
                "cause": "Edge DNS resolver intermittent timeout.",
                "confidence": 0.34,
                "evidence_for": [{"description": "socket.gaierror in logs", "tool_call": "query_logs", "source_row": "logs.csv:2"}],
                "evidence_against": [],
            },
            {
                "rank": 3,
                "cause": "Worker node 4 transient CPU throttling.",
                "confidence": 0.22,
                "evidence_for": [{"description": "node 4 CPU burst 94%", "tool_call": "query_logs", "source_row": "logs.csv:3"}],
                "evidence_against": [],
            },
        ],
        "proposed_fix": {
            "fix_id": "fix_escalate_human_operator",
            "action": "Page Tier-3 Network/Infra On-Call engineer for manual packet capture.",
            "risk_level": 0,
            "blast_radius": "Zero traffic alteration; pages on-call engineer and schedules read-only diagnostics.",
            "rationale": "Conflicting signals preclude automated remediation; confidence below 40%.",
        },
    }
    db.update_investigation(inv_id, status="completed", result_json=result)
    return inv_id


class TestEscalationPath:
    """Phase 10 escalation action on the approve endpoint."""

    def test_escalate_returns_200_and_status(self, client: TestClient, user_credentials):
        """Escalating an ambiguous investigation returns HTTP 200 with status=escalated."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        inv_id = _create_escalate_investigation(user["id"])

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            cookies={"session": session},
            json={
                "investigation_id": inv_id,
                "action": "escalate",
                "csrf_token": csrf,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "escalated"
        assert data["investigation_id"] == inv_id

    def test_escalate_writes_audit_entry(self, client: TestClient, user_credentials):
        """Escalation writes a 'fix_escalated' audit entry in the database."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        inv_id = _create_escalate_investigation(user["id"])

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            cookies={"session": session},
            json={
                "investigation_id": inv_id,
                "action": "escalate",
                "csrf_token": csrf,
            },
        )
        assert r.status_code == 200

        # Read audit log directly from the DB (same pattern as test_risk_ladder.py)
        logs = db.get_audit_log(limit=20)
        actions = [log["action"] for log in logs]
        assert "fix_escalated" in actions
        # Also verify target_id matches our investigation
        inv_entries = [log for log in logs if log["action"] == "fix_escalated" and log["target_id"] == str(inv_id)]
        assert len(inv_entries) == 1

    def test_escalate_requires_auth(self, client: TestClient):
        """Escalation without a session returns 401."""
        r = client.post(
            "/api/investigations/1/approve",
            json={
                "investigation_id": 1,
                "action": "escalate",
                "csrf_token": "x" * 32,
            },
        )
        assert r.status_code == 401

    def test_escalate_requires_csrf(self, client: TestClient, user_credentials):
        """Escalation with wrong CSRF token returns 403."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None
        inv_id = _create_escalate_investigation(user["id"])

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            cookies={"session": session},
            json={
                "investigation_id": inv_id,
                "action": "escalate",
                "csrf_token": "wrong" * 8,
            },
        )
        assert r.status_code == 403

    def test_escalate_invalid_investigation_returns_404(self, client: TestClient, user_credentials):
        """Escalating a non-existent investigation returns 404."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        r = client.post(
            "/api/investigations/999999/approve",
            cookies={"session": session},
            json={
                "investigation_id": 999999,
                "action": "escalate",
                "csrf_token": csrf,
            },
        )
        assert r.status_code == 404

    def test_escalate_already_decided_returns_400(self, client: TestClient, user_credentials):
        """Escalating an already-escalated investigation returns 400."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None
        inv_id = _create_escalate_investigation(user["id"])

        # First escalation
        r1 = client.post(
            f"/api/investigations/{inv_id}/approve",
            cookies={"session": session},
            json={"investigation_id": inv_id, "action": "escalate", "csrf_token": csrf},
        )
        assert r1.status_code == 200

        # Second attempt should be blocked
        csrf2 = get_csrf_cookie(client)
        r2 = client.post(
            f"/api/investigations/{inv_id}/approve",
            cookies={"session": session},
            json={"investigation_id": inv_id, "action": "escalate", "csrf_token": csrf2},
        )
        assert r2.status_code == 400


class TestAmbiguousEscalateScenario:
    """Verify the mock agent produces low-confidence results for ambiguous_escalate."""

    @pytest.mark.asyncio
    async def test_mock_agent_top_confidence_below_50_pct(self):
        """Mock agent for ambiguous_escalate has top hypothesis confidence < 0.50."""
        from app.agent import AgentRunner
        runner = AgentRunner("ambiguous_escalate")
        events = []
        async for event in runner.run():
            events.append(event)
        completed = next((e for e in events if e.get("type") == "investigation_completed"), None)
        assert completed is not None
        result = completed.get("result", {})
        hypotheses = result.get("hypotheses", [])
        assert len(hypotheses) >= 1
        top_confidence = hypotheses[0].get("confidence", 1.0)
        assert top_confidence < 0.50, (
            f"Expected top confidence < 0.50 for escalate scenario, got {top_confidence}"
        )

    @pytest.mark.asyncio
    async def test_mock_agent_proposed_fix_is_safe_read_only(self):
        """The ambiguous_escalate fix is risk_level 0 (read-only page/diagnostic)."""
        from app.agent import AgentRunner
        runner = AgentRunner("ambiguous_escalate")
        events = []
        async for event in runner.run():
            events.append(event)
        completed = next((e for e in events if e.get("type") == "investigation_completed"), None)
        assert completed is not None
        proposed_fix = completed.get("result", {}).get("proposed_fix", {})
        assert proposed_fix.get("risk_level") == 0
        assert "escalate" in proposed_fix.get("fix_id", "").lower() or "human" in proposed_fix.get("fix_id", "").lower()
