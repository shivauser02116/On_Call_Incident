"""
OnCall Rehearsal Agent — Security Middleware

Applies on every response:
  - Security headers (CSP, XCTO, XFO, Referrer-Policy, Permissions-Policy, HSTS)
  - Request body size limit (1 MB)
  - CORS restricted to configured origin

Rate limiting is configured in main.py via slowapi.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.config import get_settings

settings = get_settings()

MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024  # 1 MB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Inject security headers on every response.

    CSP is strict:
      - default-src 'self'
      - script-src 'self' only (no inline, no eval, no CDN)
      - style-src 'self' 'unsafe-inline' (allow inline styles for dark theme)
      - img-src 'self' data: (for SVG data URIs)
      - connect-src 'self' (SSE streams are same-origin)
      - frame-ancestors 'none' (also set X-Frame-Options: DENY)
    """

    _CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none';"
    )

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)

        response.headers["Content-Security-Policy"] = self._CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["X-XSS-Protection"] = "0"  # Modern browsers don't need it; can be harmful

        if settings.PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Remove server identification headers if present
        if "server" in response.headers:
            del response.headers["server"]
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with body larger than MAX_REQUEST_BODY_BYTES."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)
