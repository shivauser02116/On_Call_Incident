"""
OnCall Rehearsal Agent — Auth Routes

Public (unauthenticated) routes:
  GET  /health   → health check
  GET  /login    → serve login.html
  POST /login    → authenticate, set session cookie
  POST /logout   → invalidate session
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app import auth, database as db
from app.auth import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    authenticate_user,
    create_session_token,
    destroy_session,
    generate_csrf_token,
    set_csrf_cookie,
    verify_csrf_token,
)
from app.models import LoginRequest

router = APIRouter()


@router.get("/health", include_in_schema=False)
async def health() -> dict:
    """Health check — no auth required."""
    return {"status": "ok"}


@router.get("/login", include_in_schema=False)
async def login_page(request: Request) -> Response:
    """Serve the login HTML page and set a fresh CSRF cookie."""
    response = FileResponse("static/login.html")
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/login", include_in_schema=False)
async def login(request: Request, body: LoginRequest) -> Response:
    """
    Authenticate a user.

    Security:
    - CSRF double-submit cookie verified first
    - Brute-force lockout after 5 failures (15 min)
    - Generic error messages (no user enumeration)
    - IP and user-agent captured for session
    - Audit log entry written
    """
    # 1. Verify CSRF
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(body.csrf_token, csrf_cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

    # 2. Authenticate
    user = authenticate_user(body.username, body.password)
    if not user:
        # Same message whether user doesn't exist, wrong password, or locked
        db.log_audit(
            action="login_failed",
            details={"username": body.username[:64]},
            ip_address=_client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # 3. Create session
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    create_session_token(
        user_id=user["id"],
        response=response,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:256],
    )

    # 4. Refresh CSRF token (bound to new session)
    new_csrf = generate_csrf_token()
    set_csrf_cookie(response, new_csrf)

    # 5. Audit log
    db.log_audit(
        action="login_success",
        user_id=user["id"],
        ip_address=_client_ip(request),
    )

    return response


@router.post("/logout", include_in_schema=False)
async def logout(request: Request) -> Response:
    """Invalidate the current session and redirect to login."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if token:
        user = auth.validate_session(request)
        destroy_session(token, response)
        if user:
            db.log_audit(
                action="logout",
                user_id=user.user_id,
                ip_address=_client_ip(request),
            )
    return response


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.client.host if request.client else "unknown")[:45]
