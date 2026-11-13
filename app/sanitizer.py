"""
OnCall Rehearsal Agent — Telemetry Sanitizer & Injection Guard (Phase 11)

Protects against prompt injection attacks hiding inside log lines,
commit messages, deploy diffs, and team incident memories.
"""
from __future__ import annotations

import re
from typing import Any, Optional

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+|previous\s+|prior\s+)?instructions[^\.\n;]*", re.IGNORECASE),
    re.compile(r"system\s+override[^\.\n;]*", re.IGNORECASE),
    re.compile(r"instruction\s+override[^\.\n;]*", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+|previous\s+|prior\s+)?instructions[^\.\n;]*", re.IGNORECASE),
    re.compile(r"assistant:\s*i\s+will[^\.\n;]*", re.IGNORECASE),
    re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*script\b[^>]*>", re.IGNORECASE),
]


def detect_and_neutralize(text: str) -> tuple[str, Optional[str]]:
    """
    Check if a string contains known prompt injection markers.
    If detected, replaces the marker with a safe sanitized placeholder
    and returns (neutralized_text, short_excerpt).
    Otherwise returns (text, None).
    """
    if not text or not isinstance(text, str):
        return (text, None)

    neutralized = text
    first_excerpt: Optional[str] = None

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(neutralized)
        if match:
            raw_match = match.group(0).strip()
            # Clean excerpt for safe display (no raw control chars)
            clean_excerpt = re.sub(r"[\r\n\t]+", " ", raw_match)[:80]
            if first_excerpt is None:
                first_excerpt = clean_excerpt
            neutralized = pattern.sub("[UNTRUSTED_INSTRUCTION_BLOCKED]", neutralized)

    return (neutralized, first_excerpt)


def scan_payload_for_injections(data: Any) -> list[str]:
    """Recursively scan an object (dict, list, string) and return any found injection excerpts."""
    excerpts: list[str] = []
    if isinstance(data, str):
        _, exc = detect_and_neutralize(data)
        if exc:
            excerpts.append(exc)
    elif isinstance(data, dict):
        for v in data.values():
            excerpts.extend(scan_payload_for_injections(v))
    elif isinstance(data, list):
        for item in data:
            excerpts.extend(scan_payload_for_injections(item))
    return excerpts
