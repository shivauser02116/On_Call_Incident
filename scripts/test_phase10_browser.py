#!/usr/bin/env python3
"""
Phase 10 Browser Verification Script

Tests:
  A. Escalation path: ambiguous_escalate scenario shows "No safe fix found" and
     "Escalate to a human" button on the Decision screen (not Approve).
  B. Escalate action writes an audit entry (confirmed via admin audit log API).
  C. Stopwatch screen: "Compare with manual" button on Theories navigates to
     stopwatch, raw logs load, start/stop timer works, result strip appears.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AGENTX_DIR = Path("/Users/shivaprasad/Downloads/AgentX")
SCREENSHOTS_DIR = Path("/Users/shivaprasad/.gemini/antigravity/brain/ae22b418-2b88-4246-9c98-5cd7487c1c00/browser_screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = Path("/tmp/e2e_phase10_test.db")
TEST_PORT = 8198
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

if TEST_DB.exists():
    TEST_DB.unlink()

sys.path.insert(0, str(AGENTX_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AGENT_MODE"] = "mock"
os.environ["SECRET_KEY"] = "e2e-browser-p10-secret-key-at-least-32-chars!"
os.environ["PRODUCTION"] = "false"
os.environ["ANTHROPIC_API_KEY"] = "mock-key-not-used"

from app.database import init_db, create_user
from app.auth import hash_password

init_db()
create_user("admin", hash_password("AdminPass1234!"), role="admin")

env = os.environ.copy()
env["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
env["AGENT_MODE"] = "mock"
env["SECRET_KEY"] = "e2e-browser-p10-secret-key-at-least-32-chars!"
env["PRODUCTION"] = "false"
env["CORS_ORIGIN"] = BASE_URL

server_proc = subprocess.Popen(
    ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(TEST_PORT)],
    cwd=str(AGENTX_DIR),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Poll until server is ready (max 15 s)
for _attempt in range(30):
    try:
        urllib.request.urlopen(f"{BASE_URL}/login", timeout=1)
        break
    except Exception:
        time.sleep(0.5)
else:
    print("ERROR: server did not become ready in time")
    server_proc.terminate()
    sys.exit(1)

results: list[tuple[str, bool, str]] = []

def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f": {detail}" if detail else ""))

try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception:
            browser = pw.chromium.launch(
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
        ctx = browser.new_context(viewport={"width": 1280, "height": 950})
        page = ctx.new_page()
        page.set_default_timeout(15_000)

        # ── Helper: login ─────────────────────────────────────────────────
        def login(username="admin", password="AdminPass1234!"):
            page.goto(f"{BASE_URL}/login")
            page.wait_for_selector('input[type="text"]')
            page.fill('input[type="text"]', username)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_url(lambda u: "alert" in u, timeout=10_000)

        def screenshot(name: str):
            path = SCREENSHOTS_DIR / name
            page.screenshot(path=str(path))
            return str(path)

        # ── SECTION A: Escalation path ────────────────────────────────────
        print("\nSection A: Escalation path (ambiguous_escalate scenario)")
        login()

        # Navigate to Alert, pick ambiguous_escalate
        page.wait_for_selector("select")
        page.select_option("select", "ambiguous_escalate")
        time.sleep(0.3)

        # Click Start investigation
        page.click("button:has-text('Start investigation')")
        # Wait on Investigate screen for completion
        page.wait_for_selector("text=Checks complete. Review the findings, then continue.", timeout=20_000)
        check("A1 investigation completes on ambiguous_escalate", True)

        # Click "See likely causes"
        page.click("button:has-text('See likely causes')")
        page.wait_for_url(lambda u: "theories" in u, timeout=8_000)
        check("A2 navigate to Theories", True)

        # Click "Review fix"
        page.click("button:has-text('Review fix')")
        page.wait_for_url(lambda u: "fix" in u, timeout=8_000)
        # Click through fix screen
        page.click("button:has-text('Continue to decision')")
        page.wait_for_url(lambda u: "decision" in u, timeout=8_000)

        # Decision screen should show "No safe fix found" (top confidence = 38%)
        page.wait_for_selector("text=No safe fix found", timeout=8_000)
        check("A3 Decision shows 'No safe fix found'", True)
        screenshot("15_decision_no_safe_fix.png")

        # Approve button should NOT be present; Escalate should be
        approve_count = page.locator("button:has-text('Approve fix')").count()
        escalate_count = page.locator("[data-testid='escalate-button']").count()
        check("A4 Approve button absent", approve_count == 0, f"count={approve_count}")
        check("A5 Escalate button present", escalate_count >= 1, f"count={escalate_count}")
        screenshot("16_decision_escalate_button.png")

        # Click Escalate
        page.click("[data-testid='escalate-button']")
        page.wait_for_selector("text=Escalated to a human", timeout=8_000)
        check("A6 After escalation shows confirmation", True)
        screenshot("17_escalated_confirmation.png")

        # ── SECTION B: Audit entry ────────────────────────────────────────
        print("\nSection B: Audit entry after escalation")
        import requests as _req
        # Get session cookie
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        session_val = cookies.get("session", "")
        resp = _req.get(
            f"{BASE_URL}/admin/audit-log",
            cookies={"session": session_val},
            timeout=5,
        )
        if resp.status_code == 200:
            check("B1 admin audit-log accessible", True)
            entries = resp.json().get("entries", [])
            actions = [e.get("action") for e in entries]
            has_escalate = "fix_escalated" in actions
            check("B2 audit log contains escalation action", has_escalate, f"actions found: {actions}")
        else:
            check("B1 admin audit-log accessible", False, f"HTTP {resp.status_code}")
            check("B2 audit log contains escalation action", False)

        # ── SECTION C: Stopwatch / Compare with manual ────────────────────
        print("\nSection C: Stopwatch screen")

        # Go back to Theories for a normal (non-escalate) scenario
        page.goto(f"{BASE_URL}/#alert")
        page.wait_for_selector("select")
        page.select_option("select", "bad_deploy_slow_queries")
        time.sleep(0.3)
        page.click("button:has-text('Start investigation')")
        page.wait_for_selector("text=Checks complete. Review the findings, then continue.", timeout=20_000)
        page.click("button:has-text('See likely causes')")
        page.wait_for_url(lambda u: "theories" in u, timeout=8_000)
        check("C1 on Theories screen (normal scenario)", True)
        screenshot("18_theories_with_compare.png")

        # "Compare with manual" button should be visible
        compare_btn = page.locator("[data-testid='compare-manual-btn']")
        check("C2 'Compare with manual' button visible", compare_btn.count() >= 1)

        # Click it
        compare_btn.click()
        page.wait_for_url(lambda u: "stopwatch" in u, timeout=8_000)
        check("C3 navigate to Stopwatch screen", True)

        # Raw log viewer should load
        page.wait_for_selector("[data-testid='log-viewer']", timeout=10_000)
        log_lines = page.locator("[data-testid='log-viewer'] > div").count()
        check("C4 raw logs loaded", log_lines > 0, f"lines={log_lines}")
        screenshot("19_stopwatch_logs.png")

        # Filter works
        page.fill("[data-testid='log-filter']", "ERROR")
        time.sleep(0.5)
        filtered_lines = page.locator("[data-testid='log-viewer'] > div").count()
        check("C5 filter narrows logs", filtered_lines < log_lines or filtered_lines == 0,
              f"filtered={filtered_lines} of {log_lines}")

        # Clear filter
        page.click("button:has-text('Clear')")
        time.sleep(0.3)

        # Stopwatch: start
        page.click("[data-testid='start-stopwatch']")
        time.sleep(1.2)
        display_text = page.locator("[data-testid='stopwatch-display']").text_content()
        check("C6 stopwatch started and ticking", display_text != "00:00", f"display={display_text}")

        # Stop
        page.click("[data-testid='identify-button']")
        time.sleep(0.3)
        # Result strip or at least done state
        done_text = page.locator("text=Manual time:").count()
        check("C7 manual time shown after stop", done_text >= 1)
        screenshot("20_stopwatch_done.png")

        # Back button returns to Theories
        page.click("button:has-text('Back to theories')")
        page.wait_for_url(lambda u: "theories" in u, timeout=8_000)
        check("C8 Back to theories from Stopwatch", True)

        browser.close()

except Exception as exc:
    check("UNEXPECTED EXCEPTION", False, str(exc))
    import traceback
    traceback.print_exc()

finally:
    server_proc.terminate()
    server_proc.wait(timeout=5)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Phase 10 Browser Test Results")
print("=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
for name, ok, detail in results:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" ({detail})" if detail else ""))
print(f"\n{passed}/{total} passed")
print("=" * 60)

if passed < total:
    sys.exit(1)
sys.exit(0)
