"""
OnCall Rehearsal Agent — FastAPI Application Entry Point

Security hardening applied at startup:
  - Required env vars validated (refuses to start if missing)
  - SQLite file permissions set to 0o640
  - Security headers on every response
  - CORS restricted to configured origin
  - Rate limiting per-IP and per-user
  - Request body size limit (1 MB)
  - /docs and /openapi.json disabled in production
  - Generic error messages (no stack traces)
  - Only /static files are served over HTTP
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, create_user, get_user_by_username
from app.auth import hash_password
from app.middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from app.routes.admin_routes import router as admin_router
from app.routes.api_routes import router as api_router
from app.routes.auth_routes import router as auth_router

settings = get_settings()

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger(__name__)

from app.limiter import limiter

# ── Environment-driven admin seeding ───────────────────────────────────────

import os as _os
import re as _re

_USERNAME_RE = _re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")


def _seed_admin_from_env() -> None:
    """
    If ADMIN_USERNAME and ADMIN_PASSWORD env vars are set, create or update
    the admin user at startup.

    This is the ONLY way to provision users on Cloud Run where SQLite is
    ephemeral and ``create_admin.py`` cannot run interactively.

    Security notes:
    - Both variables MUST be injected via Secret Manager; never bake them
      into the Docker image or Dockerfile.
    - The password is hashed with Argon2 before storage; the plaintext value
      is immediately discarded after hashing.
    - This function never logs the password value.
    """
    username = _os.environ.get("ADMIN_USERNAME", "").strip()
    password = _os.environ.get("ADMIN_PASSWORD", "").strip()

    if not username or not password:
        return  # Not configured — skip silently

    if not _USERNAME_RE.match(username):
        log.error(
            "ADMIN_USERNAME '%s' contains invalid characters — admin seeding skipped.",
            username,
        )
        return

    if len(password) < 12:
        log.error("ADMIN_PASSWORD is too short (< 12 chars) — admin seeding skipped.")
        return

    existing = get_user_by_username(username)
    password_hash = hash_password(password)
    # Discard plaintext immediately
    del password

    if existing:
        from app.database import get_db
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, role = 'admin', "
                "failed_login_count = 0, locked_until = NULL WHERE username = ?",
                (password_hash, username),
            )
        log.info("Admin user '%s' updated from ADMIN_USERNAME/ADMIN_PASSWORD env vars.", username)
    else:
        create_user(username=username, password_hash=password_hash, role="admin")
        log.info("Admin user '%s' created from ADMIN_USERNAME/ADMIN_PASSWORD env vars.", username)


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Startup
    settings.print_startup_status()
    init_db()
    log.info("Database initialized.")
    log.info("OnCall Rehearsal Agent started. PRODUCTION=%s", settings.PRODUCTION)
    log.info(
        "Agent mode: %s (model: %s)",
        settings.AGENT_MODE.upper(),
        settings.CLAUDE_MODEL if settings.AGENT_MODE == "live" else "N/A (mock)",
    )

    # ── Environment-driven admin seeding (Cloud Run / ephemeral SQLite) ──
    # On Cloud Run, SQLite is ephemeral (reset on each new container instance).
    # Set ADMIN_USERNAME + ADMIN_PASSWORD env vars to automatically create the
    # admin user at startup without interactive prompts.
    # WARNING: These env vars must come from Secret Manager, never from the
    # Dockerfile or image. The admin account resets on every redeploy.
    _seed_admin_from_env()

    yield
    # Shutdown
    log.info("OnCall Rehearsal Agent shutting down.")


# ── App Factory ────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    # Disable /docs and /openapi.json in production
    docs_url = None if settings.PRODUCTION else "/docs"
    openapi_url = None if settings.PRODUCTION else "/openapi.json"

    app = FastAPI(
        title="OnCall Rehearsal Agent",
        description="AI on-call incident agent — simulated environment",
        version="1.0.0",
        docs_url=docs_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # ── State (rate limiter must be on app.state) ──────────────────────────
    app.state.limiter = limiter

    # ── Middleware (order matters: outermost = first to process request) ───
    # 1. Request size limit (before anything else reads the body)
    app.add_middleware(RequestSizeLimitMiddleware)

    # 2. Security headers (wraps every response)
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. CORS — restrict to our own origin only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CORS_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        expose_headers=[],
    )

    # ── Error Handlers ─────────────────────────────────────────────────────
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Not found"},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Internal server error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Routers ────────────────────────────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(api_router)

    # ── Static Files & SPA Fallback ────────────────────────────────────────
    import os

    # Mount frontend dist assets if built, and preserve /static directory
    if os.path.isdir("frontend/dist/assets"):
        app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

    # ONLY serve the static/ directory.
    # data/, oncall.db, .env, .git are NOT mounted and return 404.
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/favicon.png", include_in_schema=False)
    async def favicon() -> Response:
        from fastapi.responses import FileResponse
        if os.path.isfile("frontend/dist/favicon.png"):
            return FileResponse("frontend/dist/favicon.png")
        if os.path.isfile("static/favicon.png"):
            return FileResponse("static/favicon.png")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Not found"})

    # Root → redirect to login if not authenticated, or index if authenticated
    @app.get("/", include_in_schema=False)
    async def root(request: Request) -> Response:
        from app.auth import validate_session, generate_csrf_token, set_csrf_cookie, CSRF_COOKIE_NAME
        from fastapi.responses import FileResponse, RedirectResponse
        user = validate_session(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        dist_html = "frontend/dist/index.html"
        file_path = dist_html if os.path.isfile(dist_html) else "static/index.html"
        response = FileResponse(file_path)
        if not request.cookies.get(CSRF_COOKIE_NAME):
            csrf_token = generate_csrf_token()
            set_csrf_cookie(response, csrf_token)
        return response

    # SPA route fallback for UI routes
    UI_ROUTES = frozenset({"alert", "investigate", "theories", "fix", "decision", "success", "profile"})

    @app.get("/{ui_path}", include_in_schema=False)
    async def spa_route_fallback(request: Request, ui_path: str) -> Response:
        from app.auth import validate_session, generate_csrf_token, set_csrf_cookie, CSRF_COOKIE_NAME
        from fastapi.responses import FileResponse, RedirectResponse
        if ui_path not in UI_ROUTES:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Not found"})
        user = validate_session(request)
        if not user:
            return RedirectResponse(url=f"/login#{ui_path}", status_code=302)
        dist_html = "frontend/dist/index.html"
        file_path = dist_html if os.path.isfile(dist_html) else "static/index.html"
        response = FileResponse(file_path)
        if not request.cookies.get(CSRF_COOKIE_NAME):
            csrf_token = generate_csrf_token()
            set_csrf_cookie(response, csrf_token)
        return response

    return app


app = create_app()
