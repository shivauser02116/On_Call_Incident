#!/usr/bin/env python3
"""
OnCall Rehearsal Agent — Admin User Creation CLI

Usage:
    python create_admin.py
    python create_admin.py --force   # overwrite existing admin

Prompts for username and password interactively.
Never echoes the password to the terminal.
Refuses to create a user if one already exists (unless --force).
"""
from __future__ import annotations

import argparse
import getpass
import re
import sys
from pathlib import Path

# Ensure we can import from the app directory
sys.path.insert(0, str(Path(__file__).parent))

from app.auth import hash_password
from app.config import get_settings
from app.database import create_user, get_user_by_username, init_db, invalidate_all_user_sessions

settings = get_settings()

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or reset the admin user for OnCall Rehearsal Agent"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing admin user (invalidates all sessions)",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Admin username (will prompt if not provided)",
    )
    return parser.parse_args()


def validate_username(username: str) -> None:
    if not USERNAME_PATTERN.match(username):
        print(
            "ERROR: Username must be 1-64 characters, only letters, digits, _, -, and ."
        )
        sys.exit(1)


def validate_password(password: str, confirm: str) -> None:
    if password != confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)
    if len(password) < PASSWORD_MIN_LENGTH:
        print(f"ERROR: Password must be at least {PASSWORD_MIN_LENGTH} characters.")
        sys.exit(1)
    if len(password) > PASSWORD_MAX_LENGTH:
        print(f"ERROR: Password must be at most {PASSWORD_MAX_LENGTH} characters.")
        sys.exit(1)
    # Basic strength check
    if not any(c.isupper() for c in password):
        print("ERROR: Password must contain at least one uppercase letter.")
        sys.exit(1)
    if not any(c.islower() for c in password):
        print("ERROR: Password must contain at least one lowercase letter.")
        sys.exit(1)
    if not any(c.isdigit() for c in password):
        print("ERROR: Password must contain at least one digit.")
        sys.exit(1)


def main() -> None:
    args = parse_args()

    print("=" * 50)
    print("OnCall Rehearsal Agent — Create Admin")
    print("=" * 50)

    # Initialize database
    init_db()

    # Get username
    if args.username:
        username = args.username.strip()
    else:
        username = input("Admin username: ").strip()

    validate_username(username)

    # Check for existing user
    existing = get_user_by_username(username)
    if existing:
        if existing["role"] != "admin":
            print(f"ERROR: User '{username}' exists but is not an admin.")
            sys.exit(1)
        if not args.force:
            print(
                f"ERROR: Admin user '{username}' already exists. "
                "Use --force to overwrite."
            )
            sys.exit(1)
        print(f"WARNING: Overwriting existing admin user '{username}'.")

    # Get password (never echoed)
    print("\nPassword requirements:")
    print(f"  - Minimum {PASSWORD_MIN_LENGTH} characters")
    print("  - At least one uppercase letter")
    print("  - At least one lowercase letter")
    print("  - At least one digit")
    print()

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    validate_password(password, confirm)

    # Hash and store
    password_hash = hash_password(password)

    if existing and args.force:
        # Update existing user
        from app.database import get_db
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL WHERE username = ?",
                (password_hash, username),
            )
        # Invalidate all sessions for this user
        invalidate_all_user_sessions(existing["id"])
        print(f"\nAdmin user '{username}' updated successfully.")
        print("All existing sessions have been invalidated.")
    else:
        user_id = create_user(username=username, password_hash=password_hash, role="admin")
        print(f"\nAdmin user '{username}' created successfully (id={user_id}).")

    print("\nYou can now start the app and log in with these credentials.")
    print("=" * 50)


if __name__ == "__main__":
    main()
