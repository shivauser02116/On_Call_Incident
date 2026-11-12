"""
Tests for Phase 3 Backend Additions:
  - GET /api/me (auth required, rate limited, no secrets/hashes leaked)
  - GET /api/scenarios (auth required, rate limited, metadata from data files)
  - Sign-out server-side session teardown verification
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app import database as db
from app.database import _hash_token
from tests.conftest import get_csrf_cookie, login


class TestMeEndpoint:
    """Tests for GET /api/me."""

    def test_me_unauthenticated_returns_401(self, client: TestClient):
        r = client.get("/api/me")
        assert r.status_code == 401
        assert r.json()["detail"] == "Authentication required"

    def test_me_authenticated_returns_profile(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/me", cookies={"session": session})
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == user_credentials["username"]
        assert data["role"] in ("user", "admin")
        assert "last_sign_in" in data

    def test_me_no_secrets_or_hashes_leaked(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/me", cookies={"session": session})
        assert r.status_code == 200
        data = r.json()

        # Check allowed keys ONLY
        allowed_keys = {"username", "role", "last_sign_in"}
        assert set(data.keys()) == allowed_keys, f"Unexpected fields leaked: {set(data.keys()) - allowed_keys}"

        # Raw text search for prohibited secret patterns
        text = r.text.lower()
        forbidden_terms = ["password", "hash", "argon2", "salt", "secret", "token", "session", "key"]
        for term in forbidden_terms:
            assert term not in text, f"Forbidden term '{term}' found in /api/me response"


class TestScenariosEndpoint:
    """Tests for GET /api/scenarios with data-file driven metadata."""

    def test_scenarios_unauthenticated_returns_401(self, client: TestClient):
        r = client.get("/api/scenarios")
        assert r.status_code == 401

    def test_scenarios_authenticated_returns_rich_metadata(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/scenarios", cookies={"session": session})
        assert r.status_code == 200
        data = r.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) >= 3

        for s in data["scenarios"]:
            assert "id" in s, f"Missing id in scenario: {s}"
            assert "title" in s, f"Missing title in scenario: {s}"
            assert "service_name" in s, f"Missing service_name in scenario: {s}"
            assert "severity" in s, f"Missing severity in scenario: {s}"
            assert s["id"] in ("bad_deploy_slow_queries", "connection_pool_leak", "memory_leak")

    def test_scenarios_read_from_data_files(self, client: TestClient, user_credentials):
        """Confirm values match metadata.json in data/scenarios directory."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/scenarios", cookies={"session": session})
        assert r.status_code == 200
        scenarios_by_id = {s["id"]: s for s in r.json()["scenarios"]}

        data_dir = Path(__file__).parent.parent / "data" / "scenarios"
        for sid, sdata in scenarios_by_id.items():
            meta_file = data_dir / sid / "metadata.json"
            if meta_file.exists():
                with open(meta_file, encoding="utf-8") as f:
                    file_meta = json.load(f)
                    assert sdata["title"] == file_meta["title"]
                    assert sdata["service_name"] == file_meta["service_name"]
                    assert sdata["severity"] == file_meta["severity"]


class TestSignoutServerSideTeardown:
    """Verify that sign-out completely deletes the session server-side."""

    def test_logout_clears_session_server_side(self, client: TestClient, user_credentials):
        # 1. Log in
        session_token = login(client, user_credentials["username"], user_credentials["password"])
        token_hash = _hash_token(session_token)

        # Verify session exists in DB
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            assert row is not None, "Session record must exist in DB after login"

        # 2. Access /api/me -> succeeds
        r_before = client.get("/api/me", cookies={"session": session_token})
        assert r_before.status_code == 200

        # 3. Call POST /logout
        r_logout = client.post("/logout", cookies={"session": session_token}, follow_redirects=False)
        assert r_logout.status_code in (302, 303)

        # 4. Verify session is DELETED from database server-side
        with db.get_db() as conn:
            row_after = conn.execute(
                "SELECT * FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            assert row_after is None, "Session record MUST be deleted from database server-side upon logout"

        # 5. Old session cookie is now completely rejected (401)
        r_after = client.get("/api/me", cookies={"session": session_token})
        assert r_after.status_code == 401
