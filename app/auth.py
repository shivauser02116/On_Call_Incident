"""
OnCall Rehearsal Agent — Authentication & Session Management

- Password hashing: argon2-cffi (PasswordHasher)
- Session tokens: secrets.token_urlsafe(32), stored as SHA-256 hash
- Cookie settings: HttpOnly, SameSite=Strict, Secure in production
- CSRF: double-submit cookie pattern
- Brute force: 5 failures → 15-minute lockout
- Session expiry: 8 hours
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import Cookie, HTTPException, Request, status
from fastapi.responses import Response

from app import database as db
from app.config import get_settings

settings = get_settings()

# Argon2 parameters — OWASP recommended minimum
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

SESSION_COOKIE_NAME = "session"
CSRF_COOKIE_NAME = "csrf_token"
SESSION_EXPIRY_HOURS = 8
BRUTE_FORCE_THRESHOLD = 5
LOCKOUT_MINUTES = 15


# ── Password ───────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using argon2id."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.
    Returns False on any failure — never raises to callers.
    """
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ── CSRF ───────────────────────────────────────────────────────────────────

def generate_csrf_token() -> str:
    """Generate a cryptographically random CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set the CSRF double-submit cookie (not HttpOnly so JS can read it)."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # Must be readable by JS for double-submit pattern
        secure=settings.PRODUCTION,
        samesite="strict",
        max_age=SESSION_EXPIRY_HOURS * 3600,
        path="/",
    )


def verify_csrf_token(submitted: str, cookie: Optional[str]) -> bool:
    """
    Verify CSRF using double-submit pattern.
    Both values must be present and equal (constant-time compare).
    """
    if not submitted or not cookie:
        return False
    return hmac.compare_digest(submitted, cookie)


# ── Session ────────────────────────────────────────────────────────────────

def create_session_token(
    user_id: int,
    response: Response,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """Create a new session, set the session cookie, return the token."""
    token = secrets.token_urlsafe(32)
    db.create_session(
        user_id=user_id,
        token=token,
        ip_address=ip_address,
        user_agent=user_agent,
        expiry_hours=SESSION_EXPIRY_HOURS,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.PRODUCTION,
        samesite="strict",
        max_age=SESSION_EXPIRY_HOURS * 3600,
        path="/",
    )
    return token


def destroy_session(token: str, response: Response) -> None:
    """Invalidate the session and clear the cookie."""
    db.invalidate_session(token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


# ── Current User Dependencies ──────────────────────────────────────────────

class AuthenticatedUser:
    """Minimal user context extracted from a valid session."""

    def __init__(self, user_id: int, username: str, role: str) -> None:
        self.user_id = user_id
        self.username = username
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For if trusted."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def validate_session(request: Request) -> Optional[AuthenticatedUser]:
    """
    Read session cookie, verify token, return AuthenticatedUser or None.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    row = db.get_session(token)
    if not row:
        return None
    return AuthenticatedUser(
        user_id=row["uid"],
        username=row["username"],
        role=row["role"],
    )


async def require_auth(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency: require a valid session.
    Raises 401 if not authenticated.
    """
    user = validate_session(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


async def require_admin(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency: require admin role.
    Raises 401/403 as appropriate.
    """
    user = await require_auth(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ── Login Logic ────────────────────────────────────────────────────────────

def authenticate_user(
    username: str,
    password: str,
) -> Optional[db.sqlite3.Row]:
    """
    Validate credentials with brute-force protection.
    Returns user row on success, None on failure.
    Handles locking internally.
    """
    user = db.get_user_by_username(username)
    if not user:
        # Timing-safe: perform a dummy hash to prevent user enumeration
        _ph.hash("dummy_password_to_prevent_timing_attack")
        return None

    # Check if account is locked
    if user["locked_until"]:
        locked_until = datetime.fromisoformat(user["locked_until"])
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < locked_until:
            return None  # Still locked — same generic error

    # Verify password
    if not verify_password(password, user["password_hash"]):
        count = db.increment_failed_login(username)
        if count >= BRUTE_FORCE_THRESHOLD:
            db.lock_user(username, LOCKOUT_MINUTES)
        return None

    # Success — reset failure counter
    db.reset_failed_login(username)
    return user
