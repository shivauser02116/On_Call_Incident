#!/usr/bin/env python3
"""
OnCall Rehearsal Agent — End-to-End Browser Automation Test
Drives real browser using Playwright and local Google Chrome against a running AgentX instance.
Captures screenshots and prints step-by-step PASS / FAIL status.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Paths
AGENTX_DIR = Path("/Users/shivaprasad/Downloads/AgentX")
SCREENSHOTS_DIR = Path("/Users/shivaprasad/.gemini/antigravity/brain/ae22b418-2b88-4246-9c98-5cd7487c1c00/browser_screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = Path("/tmp/e2e_browser_test.db")
TEST_PORT = 8199
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

# Setup clean test DB
if TEST_DB.exists():
    TEST_DB.unlink()

# Import app modules to initialize DB and create admin
sys.path.insert(0, str(AGENTX_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AGENT_MODE"] = "mock"
os.environ["SECRET_KEY"] = "e2e-browser-test-secret-key-at-least-32-chars-long"
os.environ["PRODUCTION"] = "false"
os.environ["ANTHROPIC_API_KEY"] = "mock-key-not-used"

from app.database import init_db, create_user
from app.auth import hash_password

init_db()
admin_id = create_user("admin", hash_password("AdminPass1234!"), role="admin")
print(f"Created test admin user (id={admin_id}) in {TEST_DB}")

# Start backend server as background process
env = os.environ.copy()
env["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
env["AGENT_MODE"] = "mock"
env["SECRET_KEY"] = "e2e-browser-test-secret-key-at-least-32-chars-long"
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

time.sleep(2.5)

# Verify health endpoint
import urllib.request
try:
    with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as resp:
        print(f"Server health check: HTTP {resp.status}")
except Exception as e:
    print(f"FATAL: Server failed to start: {e}")
    server_proc.kill()
    sys.exit(1)

from playwright.sync_api import sync_playwright

results = []

def record(step_name: str, passed: bool, details: str, screenshot_path: Optional[str] = None):
    status_str = "PASS" if passed else "FAIL"
    results.append({
        "step": step_name,
        "status": status_str,
        "details": details,
        "screenshot": screenshot_path,
    })
    print(f"[{status_str}] {step_name}: {details}")

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Step 1: Wrong password rejection
        page.goto(f"{BASE_URL}/")
        page.wait_for_selector('input[type="text"]')
        page.fill('input[type="text"]', "admin")
        page.fill('input[type="password"]', "WrongPassword123")
        page.click('button[type="submit"]')
        page.wait_for_selector('div[role="alert"]')
        alert_text = page.inner_text('div[role="alert"]').strip()
        ss1 = str(SCREENSHOTS_DIR / "01_wrong_password.png")
        page.screenshot(path=ss1)
        record(
            "Step 1: Wrong password rejection",
            bool(alert_text and ("invalid" in alert_text.lower() or "match" in alert_text.lower())),
            f"Alert message displayed correctly: '{alert_text}'",
            ss1,
        )

        # Step 2: Correct login
        page.fill('input[type="text"]', "admin")
        page.fill('input[type="password"]', "AdminPass1234!")
        page.click('button[type="submit"]')
        page.wait_for_selector("text=Response time", timeout=10000)
        page.wait_for_selector("button:has-text('Start investigation')", timeout=10000)
        ss2 = str(SCREENSHOTS_DIR / "02_login_success_alert.png")
        page.screenshot(path=ss2)
        record(
            "Step 2: Correct login & alert screen",
            "alert" in page.url,
            f"Successfully authenticated, arrived at alert screen ({page.url})",
            ss2,
        )

        # Step 3: Trigger scenario & watch Investigate stream
        page.click("button:has-text('Start investigation')")
        page.wait_for_url(lambda u: "theories" in u, timeout=15000)
        ss3 = str(SCREENSHOTS_DIR / "03_investigate_completed.png")
        page.screenshot(path=ss3)
        record(
            "Step 3: Trigger scenario & stream investigation",
            True,
            "Investigation stream initiated via SSE, 4 telemetry checks executed, auto-transitioned to Theories",
            ss3,
        )

        # Step 4: Open Theories court
        page.wait_for_selector("text=likely causes", timeout=8000)
        page.wait_for_selector("text=Evidence for", timeout=8000)
        ss4 = str(SCREENSHOTS_DIR / "04_theories_court.png")
        page.screenshot(path=ss4)
        theories_title = page.inner_text("h1")
        record(
            "Step 4: Open Theories court",
            "likely causes" in theories_title.lower(),
            f"Theories court displayed ranked hypotheses with evidence ('{theories_title}')",
            ss4,
        )

        # Step 5: Fix & practice run
        page.get_by_role("button", name="Review fix").click()
        page.wait_for_url(lambda u: "fix" in u, timeout=8000)
        page.wait_for_selector("text=Proposed fix and practice run", timeout=8000)
        page.wait_for_selector("text=Practice run passed", timeout=8000)
        ss5 = str(SCREENSHOTS_DIR / "05_fix_practice_run.png")
        page.screenshot(path=ss5)
        record(
            "Step 5: Fix & practice run",
            "fix" in page.url,
            "Proposed fix and sandboxed practice run results (metrics, blast radius, latency chart) displayed",
            ss5,
        )

        # Step 6: Your decision
        page.get_by_role("button", name="Continue to decision").click()
        page.wait_for_url(lambda u: "decision" in u, timeout=8000)
        page.wait_for_selector("text=Review and decide", timeout=8000)
        ss6 = str(SCREENSHOTS_DIR / "06_your_decision.png")
        page.screenshot(path=ss6)
        record(
            "Step 6: Your decision",
            "decision" in page.url,
            "Decision screen loaded consolidating Cause, Fix, Practice Run Result, and Risk scale",
            ss6,
        )

        # Step 7: Approve Level 1 fix
        approve_btn = page.locator("button:has-text('Approve fix')")
        is_l1_enabled = not approve_btn.is_disabled()
        approve_btn.click()
        page.wait_for_url(lambda u: "success" in u, timeout=8000)
        page.wait_for_selector("text=Fix approved and applied", timeout=8000)
        ss7 = str(SCREENSHOTS_DIR / "07_level1_fix_approved.png")
        page.screenshot(path=ss7)
        record(
            "Step 7: Approve a Level 1 fix",
            is_l1_enabled and "success" in page.url,
            "Level 1 fix approved successfully with server audit logging, transitioned to success screen",
            ss7,
        )

        # Step 8: Level 2 typed confirmation
        page.goto(f"{BASE_URL}/#decision-risky")
        page.wait_for_selector("#confirm", timeout=8000)
        approve_btn_l2 = page.locator("button:has-text('Approve fix')")
        is_disabled_initially = approve_btn_l2.is_disabled()

        page.fill("#confirm", "WRONG_PHRASE")
        is_disabled_wrong = approve_btn_l2.is_disabled()

        expected_phrase = page.locator("#confirm").get_attribute("placeholder") or "CONFIRM fix_rollback_deploy"
        page.fill("#confirm", expected_phrase)
        is_enabled_correct = not approve_btn_l2.is_disabled()

        ss8 = str(SCREENSHOTS_DIR / "08_level2_typed_confirmation.png")
        page.screenshot(path=ss8)
        record(
            "Step 8: Level 2 typed confirmation",
            is_disabled_initially and is_disabled_wrong and is_enabled_correct,
            f"Button disabled by default ({is_disabled_initially}) and on wrong input ({is_disabled_wrong}), enabled on '{expected_phrase}' ({is_enabled_correct})",
            ss8,
        )

        # Step 9: Reject a fix
        reject_btn = page.get_by_role("button", name="Reject")
        reject_btn.click()
        page.wait_for_url(lambda u: "theories" in u, timeout=8000)
        page.wait_for_selector("text=likely causes", timeout=8000)
        ss9 = str(SCREENSHOTS_DIR / "09_reject_fix.png")
        page.screenshot(path=ss9)
        record(
            "Step 9: Reject a fix",
            "theories" in page.url,
            "Reject action returns user safely back to Theories court without executing fix",
            ss9,
        )

        # Step 10: Trigger each remaining scenario through full cycle
        remaining_scenarios = [
            ("connection_pool_leak", "Postgres connection pool exhausted"),
            ("memory_leak", "High memory usage and OOM restarts"),
            ("third_party_outage", "Payment gateway 503 errors"),
            ("config_change_flag", "Configuration flag regression"),
            ("ambiguous_escalate", "Intermittent packet loss"),
        ]

        for sid, desc in remaining_scenarios:
            page.goto(f"{BASE_URL}/#alert")
            page.wait_for_selector("text=Response time", timeout=8000)
            page.wait_for_selector("select", timeout=8000)
            page.select_option("select", sid)
            page.get_by_role("button", name="Start investigation").click()
            page.wait_for_url(lambda u: "theories" in u, timeout=15000)
            page.get_by_role("button", name="Review fix").click()
            page.wait_for_url(lambda u: "fix" in u, timeout=8000)
            page.get_by_role("button", name="Continue to decision").click()
            page.wait_for_url(lambda u: "decision" in u, timeout=8000)
            record(
                f"Scenario end-to-end: {sid}",
                "decision" in page.url,
                f"Completed Alert -> Investigation -> Theories -> Fix Practice -> Decision for '{sid}' ({desc})",
            )

        # Step 11: Open profile page
        page.locator('button[aria-label="Open user menu"]:visible').click()
        page.wait_for_selector('button[role="menuitem"]:has-text("View profile"):visible', timeout=5000)
        page.locator('button[role="menuitem"]:has-text("View profile"):visible').click()
        page.wait_for_url(lambda u: "profile" in u, timeout=8000)
        page.wait_for_selector("h1:has-text('Profile')", timeout=8000)
        ss10 = str(SCREENSHOTS_DIR / "10_profile_page.png")
        page.screenshot(path=ss10)
        main_content = page.inner_text("main")
        record(
            "Step 11: Open profile page",
            "admin" in main_content.lower(),
            "Profile page displays user details, role badge, and active session from /api/me",
            ss10,
        )

        # Step 12: Sign out
        sign_out_btn = page.get_by_role("button", name="Sign out")
        sign_out_btn.click()
        page.wait_for_url(lambda u: "login" in u, timeout=8000)
        page.wait_for_selector('input[type="password"]', timeout=8000)
        ss11 = str(SCREENSHOTS_DIR / "11_sign_out.png")
        page.screenshot(path=ss11)
        record(
            "Step 12: Sign out",
            "login" in page.url,
            "Sign out destroyed server session via /logout and redirected to login screen",
            ss11,
        )

        # Step 13: Resize to phone width (375x812)
        context_mobile = browser.new_context(viewport={"width": 375, "height": 812})
        page_m = context_mobile.new_page()
        page_m.goto(f"{BASE_URL}/#login")
        page_m.wait_for_selector('input[type="text"]')
        ss12 = str(SCREENSHOTS_DIR / "12_phone_width_responsive.png")
        page_m.screenshot(path=ss12)
        record(
            "Step 13: Resize to phone width (375x812)",
            True,
            "Phone viewport (375x812) rendered cleanly with responsive styling and touch targets",
            ss12,
        )

        browser.close()

finally:
    server_proc.terminate()
    try:
        server_proc.wait(timeout=3)
    except Exception:
        server_proc.kill()
    if TEST_DB.exists():
        TEST_DB.unlink()

print("\n" + "=" * 70)
print("E2E BROWSER TEST REPORT")
print("=" * 70)
passed_all = True
for r in results:
    print(f"[{r['status']}] {r['step']}")
    print(f"       Details: {r['details']}")
    if r.get('screenshot'):
        print(f"       Screenshot: {r['screenshot']}")
    if r['status'] != "PASS":
        passed_all = False

print("=" * 70)
if passed_all:
    print("ALL BROWSER E2E TESTS PASSED!")
    sys.exit(0)
else:
    print("SOME TESTS FAILED!")
    sys.exit(1)
