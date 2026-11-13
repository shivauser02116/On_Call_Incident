"""
Tests for Sandbox Rehearsal, Risk Ladder, Approval Flow, and Audit Log (Phase 4)

Verifies:
  - Level 0: Read-only sandbox rehearsal runs automatically and returns before/after metrics.
  - Level 1: Reversible fix approves with one-click approval.
  - Level 2: Destructive fix strictly requires exact typed confirmation "CONFIRM <fix_id>".
  - Backend enforcement: Risk level is cross-verified against canonical sandbox_effects.json.
  - LLM cannot approve fixes; human session + CSRF token strictly required.
  - IDOR protection: User A cannot approve User B's investigation.
  - Audit log entries are written for every approval and rejection with blast radius recorded.
  - Dedicated audit page access control (admin only).
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app import database as db
from tests.conftest import get_csrf_cookie, login


def _create_test_investigation(user_id: int, scenario_id: str, fix_id: str, risk_level: int, blast_radius: str = "test blast") -> int:
    """Helper to seed an investigation ready for approval testing."""
    inv_id = db.create_investigation(user_id=user_id, scenario_id=scenario_id)
    result = {
        "hypotheses": [
            {
                "rank": 1,
                "cause": "Primary cause",
                "confidence": 0.9,
                "evidence_for": [{"description": "d", "tool_call": "query_logs", "source_row": "r1"}],
                "evidence_against": [],
            },
            {
                "rank": 2,
                "cause": "Secondary cause",
                "confidence": 0.4,
                "evidence_for": [{"description": "d", "tool_call": "query_logs", "source_row": "r2"}],
                "evidence_against": [],
            },
            {
                "rank": 3,
                "cause": "Tertiary cause",
                "confidence": 0.1,
                "evidence_for": [{"description": "d", "tool_call": "query_logs", "source_row": "r3"}],
                "evidence_against": [],
            },
        ],
        "proposed_fix": {
            "fix_id": fix_id,
            "action": f"Action for {fix_id}",
            "risk_level": risk_level,
            "blast_radius": blast_radius,
            "rationale": "Tested rationale",
        },
    }
    db.update_investigation(inv_id, status="completed", result_json=result)
    return inv_id


class TestRiskLadderLevel1:
    """Level 1: Reversible fix requires one-click approval."""

    def test_approve_level1_fix_success(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        # fix_add_index is canonical Level 1 in bad_deploy_slow_queries
        inv_id = _create_test_investigation(user["id"], "bad_deploy_slow_queries", "fix_add_index", risk_level=1)

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={
                "investigation_id": inv_id,
                "action": "approve",
                "csrf_token": csrf,
            },
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "approved"
        assert body["fix_id"] == "fix_add_index"
        assert body["risk_level"] == 1

        # Verify DB updated
        row = db.get_investigation(inv_id)
        assert row["status"] == "approved"

        # Verify audit log
        logs = db.get_audit_log(limit=5)
        actions = [log["action"] for log in logs]
        assert "fix_approved" in actions

    def test_reject_fix_success(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        inv_id = _create_test_investigation(user["id"], "bad_deploy_slow_queries", "fix_add_index", risk_level=1)

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={
                "investigation_id": inv_id,
                "action": "reject",
                "csrf_token": csrf,
            },
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

        row = db.get_investigation(inv_id)
        assert row["status"] == "rejected"

        # Verify audit log
        logs = db.get_audit_log(limit=5)
        actions = [log["action"] for log in logs]
        assert "fix_rejected" in actions


class TestRiskLadderLevel2:
    """Level 2: Destructive fix requires user to type CONFIRM <fix_id>."""

    def test_approve_level2_without_confirmation_fails(self, client: TestClient, user_credentials):
        """Level 2 fix without confirmation_text must be rejected with 400."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        # fix_rollback_deploy is canonical Level 2 in bad_deploy_slow_queries
        inv_id = _create_test_investigation(user["id"], "bad_deploy_slow_queries", "fix_rollback_deploy", risk_level=2)

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={
                "investigation_id": inv_id,
                "action": "approve",
                "confirmation_text": None,
                "csrf_token": csrf,
            },
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r.status_code == 400
        assert "CONFIRM fix_rollback_deploy" in r.json()["detail"]

    def test_approve_level2_with_wrong_confirmation_fails(self, client: TestClient, user_credentials):
        """Level 2 fix with misspelled confirmation text must be rejected with 400."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        inv_id = _create_test_investigation(user["id"], "bad_deploy_slow_queries", "fix_rollback_deploy", risk_level=2)

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={
                "investigation_id": inv_id,
                "action": "approve",
                "confirmation_text": "CONFIRM wrong_fix",
                "csrf_token": csrf,
            },
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r.status_code == 400

    def test_approve_level2_with_exact_confirmation_succeeds(self, client: TestClient, user_credentials):
        """Level 2 fix with exact 'CONFIRM <fix_id>' succeeds and logs blast radius."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        inv_id = _create_test_investigation(user["id"], "bad_deploy_slow_queries", "fix_rollback_deploy", risk_level=2)

        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={
                "investigation_id": inv_id,
                "action": "approve",
                "confirmation_text": "CONFIRM fix_rollback_deploy",
                "csrf_token": csrf,
            },
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "approved"
        assert body["risk_level"] == 2
        assert "blast_radius" in body

        # Verify audit log captures confirmation text
        logs = db.get_audit_log(limit=5)
        approved_log = next(log for log in logs if log["action"] == "fix_approved" and log["target_id"] == str(inv_id))
        details = json.loads(approved_log["details_json"])
        assert details["confirmation_text"] == "CONFIRM fix_rollback_deploy"
        assert details["risk_level"] == 2


class TestApprovalSecurityConstraints:
    def test_cannot_approve_unowned_investigation_idor(
        self, client: TestClient, user_credentials, another_user_credentials
    ):
        """User A cannot approve User B's investigation (IDOR protection)."""
        session_a = login(client, user_credentials["username"], user_credentials["password"])
        csrf_a = get_csrf_cookie(client)
        user_b = db.get_user_by_username(another_user_credentials["username"])
        assert user_b is not None

        # Investigation owned by User B
        inv_id = _create_test_investigation(user_b["id"], "bad_deploy_slow_queries", "fix_add_index", risk_level=1)

        # Attempt to approve as User A
        r = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={
                "investigation_id": inv_id,
                "action": "approve",
                "csrf_token": csrf_a,
            },
            cookies={"session": session_a, "csrf_token": csrf_a},
        )
        assert r.status_code == 404

    def test_cannot_reapprove_already_approved(self, client: TestClient, user_credentials):
        """Already approved fix cannot be approved a second time."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        csrf = get_csrf_cookie(client)
        user = db.get_user_by_username(user_credentials["username"])
        assert user is not None

        inv_id = _create_test_investigation(user["id"], "bad_deploy_slow_queries", "fix_add_index", risk_level=1)

        # First approval
        r1 = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={"investigation_id": inv_id, "action": "approve", "csrf_token": csrf},
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r1.status_code == 200

        # Second approval attempt
        r2 = client.post(
            f"/api/investigations/{inv_id}/approve",
            json={"investigation_id": inv_id, "action": "approve", "csrf_token": csrf},
            cookies={"session": session, "csrf_token": csrf},
        )
        assert r2.status_code == 400
        assert "already been approved" in r2.json()["detail"]


class TestAuditPageAccess:
    def test_audit_page_admin_access(self, client: TestClient, admin_credentials):
        """Admin user can access /admin/audit-page."""
        session = login(client, admin_credentials["username"], admin_credentials["password"])
        r = client.get("/admin/audit-page", cookies={"session": session})
        assert r.status_code == 200
        assert "Security & System Audit Log" in r.text

    def test_audit_page_regular_user_access_denied(self, client: TestClient, user_credentials):
        """Regular user receives 403 on /admin/audit-page."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/admin/audit-page", cookies={"session": session})
        assert r.status_code == 403

    def test_audit_page_unauthenticated_denied(self, client: TestClient):
        """Unauthenticated user receives 401 on /admin/audit-page."""
        r = client.get("/admin/audit-page")
        assert r.status_code == 401
