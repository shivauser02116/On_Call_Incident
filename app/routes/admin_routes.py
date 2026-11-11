"""
OnCall Rehearsal Agent — Admin Routes

All routes require admin role (checked server-side, not just client hints).

GET  /admin/audit-log            → paginated audit log
GET  /admin/users                → list all users
POST /admin/users/{user_id}/lock → lock a user account
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import FileResponse, JSONResponse

from app import database as db
from app.auth import AuthenticatedUser, require_admin
from app.models import AuditLogQuery, LockUserRequest
from app.auth import verify_csrf_token, CSRF_COOKIE_NAME

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-page", include_in_schema=False)
async def audit_page(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
) -> FileResponse:
    """Serve the dedicated audit log HTML page for administrators."""
    return FileResponse("static/audit.html")


@router.get("/audit-log")
async def get_audit_log(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    user_id: int | None = None,
    admin: AuthenticatedUser = Depends(require_admin),
) -> JSONResponse:
    """Return paginated audit log entries. Admin only."""
    # Validate query params
    query = AuditLogQuery(limit=min(limit, 500), offset=max(offset, 0), user_id=user_id)
    rows = db.get_audit_log(
        limit=query.limit,
        offset=query.offset,
        user_id=query.user_id,
    )
    return JSONResponse(content={
        "entries": [dict(row) for row in rows],
        "limit": query.limit,
        "offset": query.offset,
    })


@router.get("/users")
async def list_users(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
) -> JSONResponse:
    """List all users. Admin only. Does NOT return password hashes."""
    rows = db.list_users()
    users = [
        {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"],
            "failed_login_count": row["failed_login_count"],
            "locked_until": row["locked_until"],
        }
        for row in rows
    ]
    return JSONResponse(content={"users": users})


@router.post("/users/{user_id}/lock")
async def lock_user(
    request: Request,
    user_id: int = Path(ge=1),
    body: LockUserRequest = ...,
    admin: AuthenticatedUser = Depends(require_admin),
) -> JSONResponse:
    """Lock a user account. Admin only."""
    # Verify CSRF
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(body.csrf_token, csrf_cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Prevent admin from locking themselves
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot lock your own account",
        )

    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.lock_user_by_id(user_id, body.duration_minutes)
    db.invalidate_all_user_sessions(user_id)
    db.log_audit(
        action="admin_lock_user",
        user_id=admin.user_id,
        target_id=str(user_id),
        details={"duration_minutes": body.duration_minutes},
        ip_address=_client_ip(request),
    )

    return JSONResponse(content={"status": "locked", "user_id": user_id})


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.client.host if request.client else "unknown")[:45]
