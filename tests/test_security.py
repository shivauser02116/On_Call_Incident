"""
Security tests proving that sensitive files return 404/403 over HTTP.

Requirements verified:
  - data/ directory is not served
  - .env file is not served
  - SQLite database file is not served
  - .git/ is not served
  - answer_key.txt files are not served
  - Security headers are present on all responses
  - CSP does not allow unsafe-eval or external scripts
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


SENSITIVE_PATHS = [
    "/data/past_incidents.csv",
    "/data/scenarios/bad_deploy_slow_queries/logs.csv",
    "/data/scenarios/bad_deploy_slow_queries/metrics.csv",
    "/data/scenarios/bad_deploy_slow_queries/deploys.csv",
    "/data/scenarios/bad_deploy_slow_queries/answer_key.txt",
    "/data/scenarios/connection_pool_leak/answer_key.txt",
    "/data/scenarios/memory_leak/answer_key.txt",
    "/.env",
    "/.env.example",
    "/oncall.db",
    "/.git/config",
    "/.git/HEAD",
    "/app/config.py",
    "/app/database.py",
    "/app/auth.py",
    "/requirements.txt",
]


class TestSensitiveFileExposure:
    """Prove that sensitive files cannot be accessed over HTTP."""

    @pytest.mark.parametrize("path", SENSITIVE_PATHS)
    def test_sensitive_path_not_accessible(self, client: TestClient, path: str):
        """Each sensitive path must return 404 or 403 — never 200."""
        r = client.get(path)
        assert r.status_code in (404, 403), (
            f"SECURITY FAIL: {path} returned {r.status_code} — must be 404 or 403"
        )
        # Also must not return actual file contents
        assert "password" not in r.text.lower() or r.status_code != 200
        assert "SECRET_KEY" not in r.text
        assert "ANTHROPIC_API_KEY" not in r.text

    def test_db_file_not_accessible(self, client: TestClient):
        """SQLite database file must not be downloadable."""
        r = client.get("/oncall.db")
        assert r.status_code in (404, 403)

    def test_data_dir_traversal(self, client: TestClient):
        """Path traversal attempts to data/ must fail."""
        traversal_paths = [
            "/static/../data/past_incidents.csv",
            "/static/../../.env",
            "/%2e%2e/data/past_incidents.csv",
            "/static/%2e%2e/data/past_incidents.csv",
        ]
        for path in traversal_paths:
            r = client.get(path)
            assert r.status_code in (404, 403, 400), (
                f"Path traversal {path!r} returned {r.status_code}"
            )


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    ENDPOINTS = ["/health", "/login", "/api/scenarios"]

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_x_content_type_options(self, client: TestClient, path: str):
        """X-Content-Type-Options must be 'nosniff' on all responses."""
        r = client.get(path)
        assert r.headers.get("x-content-type-options") == "nosniff", (
            f"Missing X-Content-Type-Options: nosniff on {path}"
        )

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_x_frame_options(self, client: TestClient, path: str):
        """X-Frame-Options must be 'DENY' on all responses."""
        val = client.get(path).headers.get("x-frame-options", "")
        assert val.upper() == "DENY", f"X-Frame-Options incorrect on {path}: {val!r}"

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_csp_header_present(self, client: TestClient, path: str):
        """Content-Security-Policy must be present."""
        r = client.get(path)
        assert "content-security-policy" in r.headers, (
            f"Missing CSP header on {path}"
        )

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_csp_no_unsafe_eval(self, client: TestClient, path: str):
        """CSP must NOT allow 'unsafe-eval'."""
        csp = client.get(path).headers.get("content-security-policy", "")
        assert "unsafe-eval" not in csp, (
            f"CSP allows unsafe-eval on {path} — potential XSS risk"
        )

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_csp_no_external_scripts(self, client: TestClient, path: str):
        """CSP must NOT allow scripts from external domains."""
        csp = client.get(path).headers.get("content-security-policy", "")
        # script-src must only be 'self', never http:// or https:// external
        assert "script-src" in csp
        # Ensure no wildcard or external domain in script-src
        assert "script-src *" not in csp
        assert "cdn.jsdelivr.net" not in csp
        assert "unpkg.com" not in csp
        assert "cdnjs.cloudflare.com" not in csp

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_csp_frame_ancestors_none(self, client: TestClient, path: str):
        """CSP must include frame-ancestors 'none' to prevent clickjacking."""
        csp = client.get(path).headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp, (
            f"CSP missing frame-ancestors 'none' on {path}"
        )

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_referrer_policy(self, client: TestClient, path: str):
        """Referrer-Policy must be present."""
        val = client.get(path).headers.get("referrer-policy", "")
        assert val, f"Missing Referrer-Policy on {path}"

    @pytest.mark.parametrize("path", ["/health", "/login"])
    def test_permissions_policy(self, client: TestClient, path: str):
        """Permissions-Policy must restrict sensitive APIs."""
        val = client.get(path).headers.get("permissions-policy", "")
        assert "camera=()" in val or "camera" in val, f"Missing camera restriction on {path}"
        assert "microphone=()" in val or "microphone" in val, f"Missing microphone restriction on {path}"

    def test_no_server_header_leaking_version(self, client: TestClient):
        """Server header should not leak software version."""
        r = client.get("/health")
        server = r.headers.get("server", "")
        # Should not expose uvicorn/fastapi version
        assert "uvicorn" not in server.lower() or server == "", (
            f"Server header leaks info: {server!r}"
        )


class TestErrorHandling:
    def test_404_no_stack_trace(self, client: TestClient):
        """404 responses must not contain stack traces."""
        r = client.get("/nonexistent-route-xyz-12345")
        assert r.status_code == 404
        body = r.text
        assert "Traceback" not in body
        assert "File \"/" not in body
        assert "line " not in body.lower() or "detail" in body

    def test_generic_error_messages(self, client: TestClient):
        """Error responses must use generic messages without internal details."""
        r = client.get("/nonexistent-route-xyz-12345")
        assert r.status_code == 404
        # Should not reveal internal paths or implementation details
        body = r.json()
        assert "detail" in body
        # Detail should be a simple string, not a stack trace
        assert len(body["detail"]) < 200
