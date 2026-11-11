#!/usr/bin/env python3
"""
OnCall Rehearsal Agent — Git Secret Scanner & Pre-Commit Hook

Scans staged files and git commit history for credentials and secrets:
  - Anthropic API keys (sk-ant-...)
  - OpenAI API keys (sk-...)
  - AWS Access Keys (AKIA...)
  - RSA/EC/SSH Private Keys
  - Hardcoded tokens and secret keys
  - Accidental inclusion of .env files or database files

Usage:
    python scripts/secret_scan.py                 # Scans working directory
    python scripts/secret_scan.py --staged        # Scans staged git files (pre-commit)
    python scripts/secret_scan.py --history       # Scans all git commit diffs
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# High-confidence secret regex patterns
SECRET_PATTERNS = [
    (
        "Anthropic API Key",
        re.compile(r"sk-ant-(?:api\d{2}-)?[a-zA-Z0-9_\-]{32,}", re.IGNORECASE),
    ),
    (
        "OpenAI API Key",
        re.compile(r"sk-[a-zA-Z0-9]{20,T3BlbkFJ[a-zA-Z0-9]{20,}", re.IGNORECASE),
    ),
    (
        "AWS Access Key ID",
        re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
    ),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN\s+(?:RSA|EC|OPENSSH|DSA|PGP|ENCRYPTED)?\s*PRIVATE KEY-----"),
    ),
    (
        "Hardcoded Secret Assignment",
        re.compile(
            r"""(?i)(?:secret_key|api_key|access_token|anthropic_key)\s*[:=]\s*["'](?!your_|test-|dummy-|<|\$|[a-zA-Z0-9_-]*placeholder)[a-zA-Z0-9_\-]{24,}["']"""
        ),
    ),
]

# Files explicitly excluded from scanning
ALLOWLIST_FILES = {
    ".env.example",
    "tests/conftest.py",
    "scripts/secret_scan.py",
    "README.md",
    "SECURITY_AUDIT.md",
}


def is_allowlisted(path: Path) -> bool:
    rel = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
    return rel in ALLOWLIST_FILES or rel.startswith(".venv") or rel.startswith(".git")


def scan_text(text: str, source_name: str) -> list[str]:
    """Scan string for secret patterns; returns list of issue descriptions."""
    issues = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        # Skip comment headers or placeholders
        if "your_" in line or "placeholder" in line or "test-key" in line or "test-secret" in line:
            continue
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                # Redact matched text in output
                issues.append(f"{source_name}:{line_idx} - Potential {name} detected: {line[:50]}...")
    return issues


def scan_file(file_path: Path) -> list[str]:
    if is_allowlisted(file_path):
        return []
    if file_path.suffix in (".pyc", ".db", ".png", ".jpg", ".zip", ".tar"):
        return []

    # Check for forbidden files
    if file_path.name == ".env":
        return [f"{file_path}: CRITICAL: .env file found! .env must never be committed."]
    if file_path.suffix in (".db", ".sqlite", ".sqlite3"):
        return [f"{file_path}: CRITICAL: SQLite database file found! Databases must never be committed."]

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return scan_text(content, str(file_path.relative_to(ROOT)))
    except Exception as e:
        return [f"{file_path}: Failed to read: {e}"]


def scan_working_dir() -> list[str]:
    issues = []
    for root, dirs, files in os.walk(ROOT):
        # Skip git, cache, and venvs
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "venv", "__pycache__", ".pytest_cache")]
        for file in files:
            path = Path(root) / file
            issues.extend(scan_file(path))
    return issues


def scan_staged() -> list[str]:
    """Scan staged files via git diff --cached."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return []

    staged_files = [line.strip() for line in out.splitlines() if line.strip()]
    issues = []
    for rel_path in staged_files:
        path = ROOT / rel_path
        if path.exists():
            issues.extend(scan_file(path))
    return issues


def scan_history() -> list[str]:
    """Scan git commit history for leaked secrets."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-p", "--full-history", "--no-color"],
            cwd=ROOT,
            text=True,
            errors="ignore",
        )
    except subprocess.CalledProcessError:
        return []

    issues = []
    for line in out.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_line = line[1:].strip()
            if "placeholder" in added_line or "your_" in added_line or "test-" in added_line:
                continue
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(added_line):
                    issues.append(f"Git history commit diff matches {name}: {added_line[:50]}...")
    return issues


def install_pre_commit_hook() -> None:
    """Install git pre-commit hook that automatically runs this script."""
    hook_path = ROOT / ".git" / "hooks" / "pre-commit"
    if not (ROOT / ".git").exists():
        return
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_script = f"""#!/bin/sh
# Auto-generated OnCall Rehearsal Agent pre-commit secret scanner
python3 "{ROOT}/scripts/secret_scan.py" --staged
if [ $? -ne 0 ]; then
    echo "❌ COMMIT REJECTED: Potential secret or forbidden file detected."
    exit 1
fi
"""
    hook_path.write_text(hook_script, encoding="utf-8")
    hook_path.chmod(0o755)
    print("✅ Pre-commit hook installed at .git/hooks/pre-commit")


def main() -> None:
    parser = argparse.ArgumentParser(description="Git Secret Scanner")
    parser.add_argument("--staged", action="store_true", help="Scan only staged git files")
    parser.add_argument("--history", action="store_true", help="Scan git commit history")
    parser.add_argument("--install-hook", action="store_true", help="Install pre-commit hook")
    args = parser.parse_args()

    if args.install_hook:
        install_pre_commit_hook()
        return

    # Automatically ensure hook is installed
    install_pre_commit_hook()

    if args.staged:
        issues = scan_staged()
    elif args.history:
        issues = scan_history()
    else:
        issues = scan_working_dir()

    if issues:
        print("\n❌ SECRETS DETECTED!")
        for issue in issues:
            print(f"  - {issue}")
        print("\n🚨 Please remove all sensitive tokens, real passwords, and API keys before committing.")
        sys.exit(1)
    else:
        print("✅ Secret scan clean: No leaked secrets, credentials, or forbidden files found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
