"""
Pytest configuration and shared fixtures for OnCall Rehearsal Agent tests.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Point to a temp DB for all tests — never the production DB
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real-sk-ant-placeholder")
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-chars-long")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_db.name}")
os.environ.setdefault("PRODUCTION", "false")


@pytest.fixture(scope="session")
def app():
    """Create the FastAPI app with test DB."""
    from app.main import create_app
    from app.database import init_db
    init_db()
    return create_app()


@pytest.fixture
def client(app):
    """Return a fresh TestClient for each test."""
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="session")
def admin_credentials(app):
    """Create a test admin user and return credentials."""
    from app.auth import hash_password
    from app.database import create_user, get_user_by_username

    username = "test_admin"
    password = "TestAdmin123!SecurePass"

    if not get_user_by_username(username):
        create_user(username=username, password_hash=hash_password(password), role="admin")

    return {"username": username, "password": password}


@pytest.fixture(scope="session")
def user_credentials(app):
    """Create a test regular user and return credentials."""
    from app.auth import hash_password
    from app.database import create_user, get_user_by_username

    username = "test_user"
    password = "TestUser456!SecurePass"

    if not get_user_by_username(username):
        create_user(username=username, password_hash=hash_password(password), role="user")

    return {"username": username, "password": password}


@pytest.fixture(scope="session")
def another_user_credentials(app):
    """Create a second regular user for IDOR tests."""
    from app.auth import hash_password
    from app.database import create_user, get_user_by_username

    username = "test_user_b"
    password = "TestUserB789!SecurePass"

    if not get_user_by_username(username):
        create_user(username=username, password_hash=hash_password(password), role="user")

    return {"username": username, "password": password}


def get_csrf_cookie(client: TestClient) -> str:
    """Visit /login to get a CSRF cookie, return the token value."""
    r = client.get("/login")
    return r.cookies.get("csrf_token", "")


def login(client: TestClient, username: str, password: str) -> str:
    """Log in a user; return session cookie value."""
    csrf = get_csrf_cookie(client)
    r = client.post(
        "/login",
        json={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    return r.cookies.get("session", "")
