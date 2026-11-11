"""
Tests for authentication, authorization, and session management.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import get_csrf_cookie, login


class TestLogin:
    def test_login_valid_credentials(self, client, admin_credentials):
        """Valid credentials should return 303 redirect with session cookie."""
        csrf = get_csrf_cookie(client)
        r = client.post(
            "/login",
            json={
                "username": admin_credentials["username"],
                "password": admin_credentials["password"],
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code in (200, 303, 302)
        assert "session" in r.cookies

    def test_login_invalid_password(self, client, admin_credentials):
        """Wrong password should return 401 with generic error message."""
        csrf = get_csrf_cookie(client)
        r = client.post(
            "/login",
            json={
                "username": admin_credentials["username"],
                "password": "wrongpassword",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code == 401
        body = r.json()
        # Must NOT reveal whether user exists or what failed specifically
        assert "password" not in body["detail"].lower()
        assert "user" not in body["detail"].lower() or "Invalid" in body["detail"]

    def test_login_nonexistent_user(self, client):
        """Non-existent user should return 401 with generic error (no user enumeration)."""
        csrf = get_csrf_cookie(client)
        r = client.post(
            "/login",
            json={
                "username": "doesnotexist_xyz",
                "password": "anypassword",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code == 401

    def test_login_missing_csrf(self, client, admin_credentials):
        """Missing CSRF token should be rejected."""
        r = client.post(
            "/login",
            json={
                "username": admin_credentials["username"],
                "password": admin_credentials["password"],
                "csrf_token": "a" * 31,  # Too short — will fail Pydantic validation
            },
            follow_redirects=False,
        )
        assert r.status_code in (422, 403)

    def test_login_wrong_csrf(self, client, admin_credentials):
        """Wrong CSRF token (cookie mismatch) should be rejected."""
        # Get a real CSRF cookie but submit a different token
        get_csrf_cookie(client)
        r = client.post(
            "/login",
            json={
                "username": admin_credentials["username"],
                "password": admin_credentials["password"],
                "csrf_token": "a" * 43,  # Wrong token value
            },
            follow_redirects=False,
        )
        assert r.status_code in (401, 403, 422)

    def test_session_cookie_attributes(self, client, user_credentials):
        """Session cookie must be HttpOnly and SameSite=Strict."""
        csrf = get_csrf_cookie(client)
        r = client.post(
            "/login",
            json={
                "username": user_credentials["username"],
                "password": user_credentials["password"],
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code in (200, 303, 302)
        set_cookie_header = r.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie_header
        assert "samesite=strict" in set_cookie_header


class TestBruteForce:
    def test_brute_force_lockout(self, client):
        """After 5 failed logins, the account should be locked."""
        from app.auth import hash_password
        from app.database import create_user, get_user_by_username, reset_failed_login

        username = "brute_test_user"
        password = "BruteTest99!SecurePass"

        # Create fresh user
        from app.database import get_db
        with get_db() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
        create_user(username=username, password_hash=hash_password(password), role="user")

        csrf = get_csrf_cookie(client)
        # 5 wrong attempts
        for i in range(5):
            client.post(
                "/login",
                json={"username": username, "password": "wrong", "csrf_token": csrf},
                follow_redirects=False,
            )

        # 6th attempt — should still fail (locked)
        r = client.post(
            "/login",
            json={"username": username, "password": password, "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 401


class TestAuthorization:
    def test_protected_route_without_session(self, client):
        """Accessing /api/scenarios without session should return 401."""
        r = client.get("/api/scenarios", cookies={})
        assert r.status_code == 401

    def test_protected_route_with_valid_session(self, client, user_credentials):
        """Accessing /api/scenarios with valid session should return 200."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/scenarios", cookies={"session": session})
        assert r.status_code == 200
        assert "scenarios" in r.json()

    def test_admin_route_requires_admin(self, client, user_credentials):
        """Regular user accessing /admin/users should return 403."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/admin/users", cookies={"session": session})
        assert r.status_code == 403

    def test_admin_route_allows_admin(self, client, admin_credentials):
        """Admin user accessing /admin/users should return 200."""
        session = login(client, admin_credentials["username"], admin_credentials["password"])
        r = client.get("/admin/users", cookies={"session": session})
        assert r.status_code == 200

    def test_audit_log_requires_admin(self, client, user_credentials):
        """Regular user cannot access audit log."""
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/admin/audit-log", cookies={"session": session})
        assert r.status_code == 403


class TestIDOR:
    def test_user_cannot_access_other_users_investigation(
        self, client, user_credentials, another_user_credentials
    ):
        """
        User A should not be able to view User B's investigation (IDOR prevention).
        Must return 404 (not 403, to avoid confirming the resource exists).
        """
        from app.auth import hash_password
        from app.database import create_investigation, get_user_by_username

        # Create an investigation for user_b
        user_b = get_user_by_username(another_user_credentials["username"])
        assert user_b is not None
        inv_id = create_investigation(user_id=user_b["id"], scenario_id="bad_deploy_slow_queries")

        # Try to access it as user_a
        session_a = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get(f"/api/investigations/{inv_id}", cookies={"session": session_a})
        assert r.status_code == 404  # Must be 404, not 403

    def test_user_can_access_own_investigation(
        self, client, user_credentials
    ):
        """User can access their own investigation."""
        from app.database import create_investigation, get_user_by_username

        user = get_user_by_username(user_credentials["username"])
        assert user is not None
        inv_id = create_investigation(user_id=user["id"], scenario_id="memory_leak")

        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get(f"/api/investigations/{inv_id}", cookies={"session": session})
        assert r.status_code == 200


class TestLogout:
    def test_logout_invalidates_session(self, client, user_credentials):
        """After logout, the session cookie should not grant access."""
        session = login(client, user_credentials["username"], user_credentials["password"])

        # Confirm we're authenticated
        r = client.get("/api/scenarios", cookies={"session": session})
        assert r.status_code == 200

        # Logout
        client.post("/logout", cookies={"session": session}, follow_redirects=False)

        # Session should be invalid now
        r2 = client.get("/api/scenarios", cookies={"session": session})
        assert r2.status_code == 401

    def test_health_no_auth(self, client):
        """Health endpoint requires no authentication."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
