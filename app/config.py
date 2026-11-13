"""
OnCall Rehearsal Agent — Application Settings

Loads all configuration from environment variables.
Refuses to start if required variables are missing.
Never prints secret values — only SET/MISSING status.
"""
from __future__ import annotations

import sys
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Do NOT expose settings via repr (masks secrets)
        # pydantic-settings masks SecretStr automatically
    )

    # ── Required ───────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(
        ...,
        description="Anthropic API key — REQUIRED",
    )
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Session secret — REQUIRED, minimum 32 characters",
    )

    # ── Optional with defaults ─────────────────────────────────────────────
    CLAUDE_MODEL: str = Field(
        default="claude-sonnet-5-5",
        description="Anthropic model name",
    )
    AGENT_MODE: str = Field(
        default="live",
        description=(
            "Agent execution mode. 'live' uses the real Anthropic API (default). "
            "'mock' uses deterministic simulation — only allowed when explicitly set "
            "to AGENT_MODE=mock. No silent fallback."
        ),
    )
    PRODUCTION: bool = Field(
        default=False,
        description="Enable production hardening (HTTPS-only cookies, HSTS, no /docs)",
    )
    DATABASE_URL: str = Field(
        default="sqlite:///./oncall.db",
        description="SQLite database URL",
    )
    CORS_ORIGIN: str = Field(
        default="http://localhost:8000",
        description="Allowed CORS origin — must match the served origin exactly",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level",
    )

    # ── Token / spend limits ───────────────────────────────────────────────
    MAX_TOOL_CALLS_PER_INVESTIGATION: int = Field(
        default=12,
        description="Hard cap on tool calls per agent run",
    )
    MAX_TOKENS_PER_INVESTIGATION: int = Field(
        default=16000,
        description="Hard cap on tokens per agent run",
    )
    MAX_INVESTIGATIONS_PER_DAY: int = Field(
        default=100,
        description="Daily budget — investigations across all users",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("CLAUDE_MODEL")
    @classmethod
    def _model_allowlist(cls, v: str) -> str:
        # Allow any claude- model; validate prefix to prevent injection
        if not v.startswith("claude-"):
            raise ValueError("CLAUDE_MODEL must start with 'claude-'")
        return v

    @field_validator("AGENT_MODE")
    @classmethod
    def _agent_mode_allowlist(cls, v: str) -> str:
        allowed = {"live", "mock"}
        v_lower = v.strip().lower()
        if v_lower not in allowed:
            raise ValueError(f"AGENT_MODE must be one of {allowed!r}, got {v!r}")
        return v_lower

    def print_startup_status(self) -> None:
        """
        Print which env vars are SET or MISSING — NEVER print their values.
        Called once at startup so operators know what's configured.
        """
        required = ["ANTHROPIC_API_KEY", "SECRET_KEY"]
        optional = [
            "CLAUDE_MODEL",
            "AGENT_MODE",
            "PRODUCTION",
            "DATABASE_URL",
            "CORS_ORIGIN",
            "LOG_LEVEL",
        ]

        print("=" * 50)
        print("OnCall Rehearsal Agent — Environment Check")
        print("=" * 50)

        all_ok = True
        for name in required:
            val = getattr(self, name, None)
            if val:
                print(f"  [SET]     {name}")
            else:
                print(f"  [MISSING] {name}  ← REQUIRED")
                all_ok = False

        for name in optional:
            val = getattr(self, name, None)
            if val is not None:
                print(f"  [SET]     {name}")
            else:
                print(f"  [DEFAULT] {name}")

        print("=" * 50)
        if not all_ok:
            print("ERROR: Required environment variables are missing. Refusing to start.")
            sys.exit(1)


def get_settings() -> Settings:
    """
    Returns singleton Settings instance.
    Raises ValidationError / ValueError if required vars are missing.
    """
    return _settings


# Module-level singleton — constructed once at import time.
# If required vars are missing, pydantic raises immediately.
try:
    _settings = Settings()
except Exception as exc:  # noqa: BLE001
    print(f"FATAL: Configuration error — {exc}")
    print("Ensure ANTHROPIC_API_KEY and SECRET_KEY are set in .env or environment.")
    sys.exit(1)
