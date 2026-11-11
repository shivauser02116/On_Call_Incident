"""
OnCall Rehearsal Agent — Database Layer

SQLite with parameterized queries ONLY.
No ORM — explicit SQL for full control and security.
Database file permissions set to 0o640 at startup.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from app.config import get_settings

settings = get_settings()

# ── Helpers ────────────────────────────────────────────────────────────────

def _db_path() -> str:
    """Return the filesystem path of the SQLite database file."""
    url = settings.DATABASE_URL
    # Strip sqlite:/// prefix
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return "./oncall.db"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


# ── Connection ─────────────────────────────────────────────────────────────

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that opens/closes a SQLite connection."""
    conn = sqlite3.connect(
        _db_path(),
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema Initialization ──────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'user'
                            CHECK(role IN ('admin','user')),
    created_at      TEXT    NOT NULL,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    ip_address  TEXT,
    user_agent  TEXT
);

CREATE TABLE IF NOT EXISTS investigations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id     TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending','running','completed','failed','approved','rejected')),
    created_at      TEXT    NOT NULL,
    completed_at    TEXT,
    result_json     TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    action      TEXT    NOT NULL,
    target_id   TEXT,
    details_json TEXT,
    ip_address  TEXT,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash   ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at   ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_investigations_user_id ON investigations(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id      ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at   ON audit_log(created_at);
"""


def init_db() -> None:
    """Create tables and set file permissions."""
    db_path = _db_path()
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)

    # Restrict file permissions to owner read/write, group read only
    try:
        os.chmod(db_path, 0o640)
    except FileNotFoundError:
        pass  # DB not yet created (in-memory test mode)


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(
    username: str,
    password_hash: str,
    role: str = "user",
) -> int:
    """Insert a new user; return the new user id."""
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, password_hash, role, _now_iso()),
        )
        return cur.lastrowid  # type: ignore[return-value]


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    """Return the user row or None."""
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    """Return the user row or None."""
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def list_users() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT id, username, role, created_at, failed_login_count, locked_until FROM users ORDER BY id"
        ).fetchall()


def increment_failed_login(username: str) -> int:
    """Increment failed login counter; return new count."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET failed_login_count = failed_login_count + 1 WHERE username = ?",
            (username,),
        )
        row = conn.execute(
            "SELECT failed_login_count FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return row["failed_login_count"] if row else 0


def lock_user(username: str, duration_minutes: int = 15) -> None:
    """Lock a user account for duration_minutes."""
    locked_until = (_now_utc() + timedelta(minutes=duration_minutes)).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET locked_until = ? WHERE username = ?",
            (locked_until, username),
        )


def reset_failed_login(username: str) -> None:
    """Reset failed login counter and clear lock."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE username = ?",
            (username,),
        )


def lock_user_by_id(user_id: int, duration_minutes: int = 15) -> None:
    locked_until = (_now_utc() + timedelta(minutes=duration_minutes)).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET locked_until = ? WHERE id = ?",
            (locked_until, user_id),
        )


# ── Sessions ───────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(
    user_id: int,
    token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    expiry_hours: int = 8,
) -> None:
    """Store a hashed session token."""
    token_hash = _hash_token(token)
    expires_at = (_now_utc() + timedelta(hours=expiry_hours)).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (user_id, token_hash, created_at, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, token_hash, _now_iso(), expires_at, ip_address, user_agent),
        )


def get_session(token: str) -> Optional[sqlite3.Row]:
    """Return session row if token matches and is not expired."""
    token_hash = _hash_token(token)
    now = _now_iso()
    with get_db() as conn:
        return conn.execute(
            """
            SELECT s.*, u.username, u.role, u.id as uid
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token_hash = ?
              AND s.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()


def invalidate_session(token: str) -> None:
    """Delete a session by token."""
    token_hash = _hash_token(token)
    with get_db() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash,),
        )


def invalidate_all_user_sessions(user_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def purge_expired_sessions() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_now_iso(),))


# ── Investigations ─────────────────────────────────────────────────────────

def create_investigation(user_id: int, scenario_id: str) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO investigations (user_id, scenario_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (user_id, scenario_id, _now_iso()),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_investigation(
    investigation_id: int,
    status: str,
    result_json: Optional[dict[str, Any]] = None,
) -> None:
    now = _now_iso()
    with get_db() as conn:
        if result_json is not None:
            result_str = json.dumps(result_json)
            conn.execute(
                """
                UPDATE investigations
                SET status = ?, completed_at = COALESCE(completed_at, ?), result_json = ?
                WHERE id = ?
                """,
                (status, now, result_str, investigation_id),
            )
        else:
            conn.execute(
                """
                UPDATE investigations
                SET status = ?, completed_at = CASE WHEN ? IN ('completed','failed') THEN ? ELSE completed_at END
                WHERE id = ?
                """,
                (status, status, now, investigation_id),
            )


def get_investigation(investigation_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM investigations WHERE id = ?",
            (investigation_id,),
        ).fetchone()


def get_investigations_for_user(user_id: int) -> list[sqlite3.Row]:
    """Return only investigations that belong to the given user (IDOR safe)."""
    with get_db() as conn:
        return conn.execute(
            """
            SELECT id, scenario_id, status, created_at, completed_at
            FROM investigations
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()


def check_investigation_owner(investigation_id: int, user_id: int) -> bool:
    """Return True if the investigation belongs to this user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM investigations WHERE id = ? AND user_id = ?",
            (investigation_id, user_id),
        ).fetchone()
        return row is not None


# ── Audit Log ──────────────────────────────────────────────────────────────

def log_audit(
    action: str,
    user_id: Optional[int] = None,
    target_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    details_json = json.dumps(details) if details is not None else None
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (user_id, action, target_id, details_json, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, action, target_id, details_json, ip_address, _now_iso()),
        )


def get_audit_log(
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
) -> list[sqlite3.Row]:
    with get_db() as conn:
        if user_id is not None:
            return conn.execute(
                """
                SELECT a.*, u.username
                FROM audit_log a
                LEFT JOIN users u ON a.user_id = u.id
                WHERE a.user_id = ?
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        return conn.execute(
            """
            SELECT a.*, u.username
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
