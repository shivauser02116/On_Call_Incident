"""
OnCall Rehearsal Agent — Pydantic v2 Strict Models

All user-facing inputs are validated here.
Scenario IDs and fix IDs are validated against explicit allowlists.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── Allowlists ─────────────────────────────────────────────────────────────
# These are the ONLY valid values accepted from user input.
# Never construct file paths from user input directly.

ALLOWED_SCENARIOS: frozenset[str] = frozenset({
    "bad_deploy_slow_queries",
    "connection_pool_leak",
    "memory_leak",
    "third_party_outage",
    "config_change_flag",
    "ambiguous_escalate",
})

ALLOWED_FIX_IDS: frozenset[str] = frozenset({
    # bad_deploy_slow_queries
    "fix_add_index",
    "fix_rollback_deploy",
    # connection_pool_leak
    "fix_restart_app",
    "fix_connection_recycler",
    # memory_leak
    "fix_restart_service",
    "fix_patch_middleware",
    "fix_increase_memory",
    # third_party_outage
    "fix_enable_circuit_breaker",
    "fix_rollback_promo_deploy",
    # config_change_flag
    "fix_revert_config_flag",
    "fix_restart_node_cluster",
    # ambiguous_escalate
    "fix_escalate_human_operator",
    "fix_capture_diagnostics",
})


# ── Auth Models ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    username: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(min_length=1, max_length=256)
    csrf_token: str = Field(min_length=32, max_length=128)


# ── Investigation Models ───────────────────────────────────────────────────

class TriggerAlertRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    scenario_id: str = Field(min_length=1, max_length=64)
    csrf_token: str = Field(min_length=32, max_length=128)

    @property
    def validated_scenario_id(self) -> str:
        if self.scenario_id not in ALLOWED_SCENARIOS:
            raise ValueError(f"Unknown scenario: {self.scenario_id!r}")
        return self.scenario_id


class ApproveFixRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    investigation_id: int = Field(ge=1)
    action: Literal["approve", "reject", "escalate"]
    # Required for Level 2: must be "CONFIRM <fix_id>"
    confirmation_text: Optional[str] = Field(None, max_length=256)
    csrf_token: str = Field(min_length=32, max_length=128)


# ── Agent Output Models (returned from LLM, Pydantic-validated) ────────────

class EvidenceItem(BaseModel):
    model_config = ConfigDict(strict=False)  # LLM output — lenient parsing

    description: str = Field(max_length=1024)
    tool_call: str = Field(max_length=128)
    source_row: Optional[str] = Field(None, max_length=512)


class Hypothesis(BaseModel):
    model_config = ConfigDict(strict=False)

    rank: int = Field(ge=1, le=3)
    cause: str = Field(max_length=512)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_for: list[EvidenceItem] = Field(min_length=1, max_length=10)
    evidence_against: list[EvidenceItem] = Field(max_length=10)


class ProposedFix(BaseModel):
    model_config = ConfigDict(strict=False)

    fix_id: str = Field(max_length=64)
    action: str = Field(max_length=512)
    risk_level: int = Field(ge=0, le=2)
    blast_radius: str = Field(max_length=512)
    rationale: str = Field(max_length=1024)


class InvestigationResult(BaseModel):
    model_config = ConfigDict(strict=False)

    hypotheses: list[Hypothesis] = Field(min_length=3, max_length=3)
    proposed_fix: ProposedFix


# ── Admin Models ───────────────────────────────────────────────────────────

class AuditLogQuery(BaseModel):
    model_config = ConfigDict(strict=True)

    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    user_id: Optional[int] = Field(None, ge=1)


# ── Plan and Replan Models (Phase 9) ───────────────────────────────────────

class PlanStep(BaseModel):
    model_config = ConfigDict(strict=False)

    step: int = Field(default=1, ge=1, le=20)
    tool: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=512)
    id: Optional[str] = Field(default=None, max_length=64)
    label: Optional[str] = Field(default=None, max_length=128)
    reason: Optional[str] = Field(default=None, max_length=512)
    status: Literal["pending", "running", "completed", "skipped"] = "pending"


class PlanEvent(BaseModel):
    model_config = ConfigDict(strict=False)

    type: Literal["plan"] = "plan"
    source: Literal["model", "standard"] = "model"
    is_mock: Optional[bool] = None
    steps: list[PlanStep] = Field(min_length=1)


class ReplanEvent(BaseModel):
    model_config = ConfigDict(strict=False)

    type: Literal["replan"] = "replan"
    source: Literal["model", "standard"] = "model"
    is_mock: Optional[bool] = None
    reason: str = Field(max_length=1024)
    steps: list[PlanStep] = Field(min_length=1)


class LockUserRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    duration_minutes: int = Field(default=15, ge=1, le=1440)
    csrf_token: str = Field(min_length=32, max_length=128)
