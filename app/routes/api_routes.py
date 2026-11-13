"""
OnCall Rehearsal Agent — API Routes

Authenticated user routes:
  GET  /api/scenarios                       → list available scenarios
  GET  /api/scenarios/{scenario_id}/raw_logs → raw logs for manual stopwatch mode
  POST /api/investigations/trigger          → start agent investigation (SSE stream)
  GET  /api/investigations                  → user's own investigations
  GET  /api/investigations/{id}             → single investigation (IDOR check)
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app import database as db
from app.agent import AgentRunner
from app.auth import (
    AuthenticatedUser,
    CSRF_COOKIE_NAME,
    require_auth,
    verify_csrf_token,
)
from app.data_loader import (
    load_all_scenarios_metadata,
    load_logs,
    load_sandbox_effects,
    validate_scenario_id,
)
from app.limiter import limiter
from app.models import ALLOWED_FIX_IDS, ALLOWED_SCENARIOS, ApproveFixRequest, TriggerAlertRequest

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/me")
@limiter.limit("60/minute")
async def get_current_user_profile(
    request: Request,
    user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    """
    Return current authenticated user profile.
    Strictly returns: username, role, last_sign_in only.
    Never exposes password hashes, session tokens, salts, or internal secrets.
    """
    last_sign_in = db.get_last_sign_in(user.user_id)
    return JSONResponse(
        content={
            "username": user.username,
            "role": user.role,
            "last_sign_in": last_sign_in,
        }
    )


@router.get("/scenarios")
@limiter.limit("60/minute")
async def list_scenarios(
    request: Request,
    user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    """Return the list of available scenarios with metadata from data files."""
    scenarios_list = load_all_scenarios_metadata()
    return JSONResponse(content={"scenarios": scenarios_list})


@router.get("/scenarios/{scenario_id}/raw_logs")
async def get_raw_logs(
    scenario_id: str,
    user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    """Return raw logs for a scenario (used by Manual Stopwatch mode)."""
    try:
        valid_sid = validate_scenario_id(scenario_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scenario_id")

    logs = load_logs(valid_sid)
    return JSONResponse(content={"scenario_id": valid_sid, "logs": logs, "count": len(logs)})


@router.post("/investigations/trigger")
async def trigger_investigation(
    request: Request,
    body: TriggerAlertRequest,
    user: AuthenticatedUser = Depends(require_auth),
) -> StreamingResponse:
    """
    Trigger an AI investigation for a scenario and stream live progress via SSE.

    Security:
      - Double-submit CSRF token validated
      - scenario_id strictly allowlisted
      - Investigation record created with user ownership (prevents IDOR)
      - Audit log entry recorded
    """
    # 1. CSRF validation
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(body.csrf_token, csrf_cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

    # 2. Scenario allowlist validation
    try:
        scenario_id = body.validated_scenario_id
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 3. Create database record
    inv_id = db.create_investigation(user_id=user.user_id, scenario_id=scenario_id)
    client_ip = request.client.host if request.client else "unknown"

    db.log_audit(
        action="investigation_triggered",
        user_id=user.user_id,
        target_id=str(inv_id),
        details={"scenario_id": scenario_id},
        ip_address=client_ip,
    )

    # 4. SSE Generator
    async def sse_event_stream() -> AsyncGenerator[str, None]:
        runner = AgentRunner(scenario_id=scenario_id)
        # First event informs client of the database investigation id
        yield f"data: {json.dumps({'type': 'init', 'investigation_id': inv_id, 'scenario_id': scenario_id})}\n\n"

        completed_result = None
        try:
            db.update_investigation(inv_id, status="running")
            async for event in runner.run():
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "investigation_completed":
                    completed_result = event.get("result")

            if completed_result:
                db.update_investigation(inv_id, status="completed", result_json=completed_result)
            else:
                db.update_investigation(inv_id, status="failed")

        except Exception as exc:
            db.update_investigation(inv_id, status="failed")
            err_data = {"type": "error", "message": "Investigation error encountered."}
            yield f"data: {json.dumps(err_data)}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/investigations")
async def list_investigations(
    request: Request,
    user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    """Return investigations belonging to the authenticated user ONLY."""
    rows = db.get_investigations_for_user(user.user_id)
    return JSONResponse(content={
        "investigations": [
            {
                "id": row["id"],
                "scenario_id": row["scenario_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
            }
            for row in rows
        ]
    })


@router.get("/investigations/{investigation_id}")
async def get_investigation(
    request: Request,
    investigation_id: int = Path(ge=1),
    user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    """
    Return a single investigation.

    IDOR protection: ownership is checked before returning data.
    Admin can view all investigations.
    """
    if user.is_admin:
        row = db.get_investigation(investigation_id)
    else:
        # Ownership check — prevents IDOR
        if not db.check_investigation_owner(investigation_id, user.user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Investigation not found",
            )
        row = db.get_investigation(investigation_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    result = dict(row)
    if result.get("result_json"):
        try:
            result["result"] = json.loads(result["result_json"])
        except (json.JSONDecodeError, TypeError):
            result["result"] = None
    result.pop("result_json", None)

    return JSONResponse(content=result)


@router.post("/investigations/{investigation_id}/approve")
async def approve_investigation_fix(
    request: Request,
    investigation_id: int = Path(ge=1),
    body: ApproveFixRequest = ...,
    user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    """
    Approve or reject a proposed fix with backend-enforced Risk Ladder logic.

    Security & Risk Ladder:
      - Double-submit CSRF token checked
      - IDOR check: user must own investigation (or be admin)
      - Status check: must be completed
      - Backend code checks risk level from sandbox_effects.json (NEVER relies on prompt alone)
      - Level 0: Safe/Auto
      - Level 1: Reversible fix, one-click approval
      - Level 2: Destructive fix, requires user to type 'CONFIRM <fix_id>'
      - Every approval/rejection writes an audit log entry
      - The LLM can never trigger this route
    """
    # 1. CSRF validation
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(body.csrf_token, csrf_cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

    # 2. Path parameter match
    if body.investigation_id != investigation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Investigation ID mismatch between path and body",
        )

    # 3. Ownership check (IDOR protection)
    if not user.is_admin and not db.check_investigation_owner(investigation_id, user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    row = db.get_investigation(investigation_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    # 4. Status check
    current_status = row["status"]
    if current_status not in ("completed", "approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve investigation with status '{current_status}'. Must be completed first.",
        )

    if current_status in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Investigation fix has already been {current_status}.",
        )

    # 5. Extract proposed fix from result_json
    result_json_str = row["result_json"]
    if not result_json_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Investigation has no result payload.",
        )

    try:
        result_data = json.loads(result_json_str)
        proposed_fix = result_data.get("proposed_fix", {})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid investigation result format.",
        )

    fix_id = str(proposed_fix.get("fix_id", "")).strip()
    if not fix_id or fix_id not in ALLOWED_FIX_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unauthorized fix_id: '{fix_id}'",
        )

    # 6. Cross-verify risk_level from canonical sandbox_effects.json (Backend enforcement)
    scenario_id = row["scenario_id"]
    effects = load_sandbox_effects(scenario_id)
    if fix_id not in effects:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fix '{fix_id}' does not exist for scenario '{scenario_id}'.",
        )

    canonical_effect = effects[fix_id]
    risk_level = int(canonical_effect.get("risk_level", proposed_fix.get("risk_level", 1)))
    blast_radius = canonical_effect.get("blast_radius", proposed_fix.get("blast_radius", ""))

    client_ip = request.client.host if request.client else "unknown"

    # 7. Escalation flow (confidence < 50% or no confident fix found)
    if body.action == "escalate":
        db.update_investigation(investigation_id, status="rejected")
        db.log_audit(
            action="fix_escalated",
            user_id=user.user_id,
            target_id=str(investigation_id),
            details={
                "scenario_id": scenario_id,
                "fix_id": fix_id,
                "risk_level": risk_level,
                "reason": "Operator escalated to human: confidence below threshold or no safe automated fix.",
            },
            ip_address=client_ip,
        )
        return JSONResponse(content={
            "status": "escalated",
            "investigation_id": investigation_id,
            "fix_id": fix_id,
            "message": "Investigation escalated to a human operator. Audit entry recorded.",
        })

    # 8. Rejection flow
    if body.action == "reject":
        db.update_investigation(investigation_id, status="rejected")
        db.log_audit(
            action="fix_rejected",
            user_id=user.user_id,
            target_id=str(investigation_id),
            details={
                "scenario_id": scenario_id,
                "fix_id": fix_id,
                "risk_level": risk_level,
            },
            ip_address=client_ip,
        )
        return JSONResponse(content={
            "status": "rejected",
            "investigation_id": investigation_id,
            "fix_id": fix_id,
            "message": f"Fix {fix_id} was rejected by human operator.",
        })

    # 8. Approval flow & Risk Ladder enforcement
    if risk_level == 2:
        # Level 2 requires explicit typed confirmation phrase
        expected_phrase = f"CONFIRM {fix_id}"
        provided_phrase = (body.confirmation_text or "").strip()
        if provided_phrase != expected_phrase:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Level 2 destructive fix requires exact confirmation text: '{expected_phrase}'",
            )

    # Apply fix in simulation
    db.update_investigation(investigation_id, status="approved")
    db.log_audit(
        action="fix_approved",
        user_id=user.user_id,
        target_id=str(investigation_id),
        details={
            "scenario_id": scenario_id,
            "fix_id": fix_id,
            "risk_level": risk_level,
            "blast_radius": blast_radius,
            "confirmation_text": body.confirmation_text,
        },
        ip_address=client_ip,
    )

    return JSONResponse(content={
        "status": "approved",
        "investigation_id": investigation_id,
        "fix_id": fix_id,
        "risk_level": risk_level,
        "blast_radius": blast_radius,
        "message": f"Fix {fix_id} (Level {risk_level}) approved and executed in simulation.",
    })
