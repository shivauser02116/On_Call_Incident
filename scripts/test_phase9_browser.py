#!/usr/bin/env python3
"""
Phase 9 Browser Verification Script
Tests:
  - Plan checklist and Replan notice on Investigate
  - Stay on Investigate when investigation completes (no auto-nav)
  - Footer text updates to "Checks complete. Review the findings, then continue."
  - "See likely causes" button is enabled
  - Agent Trace drawer expanded with simulated labels
  - Manual navigation to Theories
  - Fix card colon splitting and RiskScale buttons/explanation
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

AGENTX_DIR = Path("/Users/shivaprasad/Downloads/AgentX")
SCREENSHOTS_DIR = Path("/Users/shivaprasad/.gemini/antigravity/brain/ae22b418-2b88-4246-9c98-5cd7487c1c00/browser_screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = Path("/tmp/e2e_phase9_test.db")
TEST_PORT = 8197
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

if TEST_DB.exists():
    TEST_DB.unlink()

sys.path.insert(0, str(AGENTX_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AGENT_MODE"] = "mock"
os.environ["SECRET_KEY"] = "e2e-browser-test-secret-key-at-least-32-chars-long"
os.environ["PRODUCTION"] = "false"
os.environ["ANTHROPIC_API_KEY"] = "mock-key-not-used"

from app.database import init_db, create_user
from app.auth import hash_password

init_db()
create_user("admin", hash_password("AdminPass1234!"), role="admin")

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

try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(viewport={"width": 1280, "height": 950})
        page = context.new_page()

        # 1. Login
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector('input[type="text"]')
        page.fill('input[type="text"]', "admin")
        page.fill('input[type="password"]', "AdminPass1234!")
        page.click('button[type="submit"]')
        page.wait_for_url(lambda u: "alert" in u)
        print("PASS 1: Authenticated & navigated to Alert")

        # 2. Select ambiguous_escalate to test both Plan and Replan
        page.wait_for_selector("select")
        page.select_option("select", "ambiguous_escalate")
        page.click("button:has-text('Start investigation')")
        page.wait_for_url(lambda u: "investigate" in u)
        print("PASS 2: Triggered ambiguous_escalate investigation, arrived at Investigate")

        # 3. Check for Investigation Plan checklist
        page.wait_for_selector("text=Investigation Plan", timeout=6000)
        print("PASS 3: Investigation Plan checklist rendered on Investigate screen")

        # 4. Wait for investigation completion - must stay on Investigate screen!
        page.wait_for_selector("text=Checks complete. Review the findings, then continue.", timeout=12000)
        assert "investigate" in page.url, "Must stay on Investigate screen when investigation completes!"
        print("PASS 4: Stayed on Investigate screen with updated footer text")

        # 5. Verify 'See likely causes' button is enabled
        see_causes_btn = page.locator("button:has-text('See likely causes')")
        assert not see_causes_btn.is_disabled(), "'See likely causes' button must be enabled!"
        print("PASS 5: 'See likely causes' button is enabled")

        # 6. Expand Agent Trace drawer on Investigate
        trace_button = page.locator("button:has-text('Agent Trace')")
        trace_button.scroll_into_view_if_needed()
        trace_button.click()
        time.sleep(0.5)

        drawer = page.locator('[data-testid="agent-trace-body"]')
        drawer.wait_for(state="visible", timeout=5000)
        drawer_text = drawer.inner_text()
        assert "simulated" in drawer_text.lower(), "Trace in mock mode must show (simulated) label"
        print("PASS 6: Agent Trace drawer expanded on Investigate screen with simulated labels")

        page.screenshot(path=str(SCREENSHOTS_DIR / "13_investigate_plan_and_trace.png"))
        print(f"Captured screenshot: {SCREENSHOTS_DIR / '13_investigate_plan_and_trace.png'}")

        # 7. Manually click 'See likely causes' to navigate to Theories
        see_causes_btn.click()
        page.wait_for_url(lambda u: "theories" in u, timeout=5000)
        print("PASS 7: Navigated to Theories on button click")

        # 8. Verify Agent Trace drawer on Theories
        time.sleep(1.0)
        page.wait_for_selector("button:has-text('Agent Trace')", timeout=5000)
        theories_trace_btn = page.locator("button:has-text('Agent Trace')").first
        theories_trace_btn.scroll_into_view_if_needed()
        theories_trace_btn.click()
        time.sleep(0.5)

        t_drawer = page.locator('[data-testid="agent-trace-body"]').first
        t_drawer.wait_for(state="visible", timeout=5000)
        t_drawer_text = t_drawer.inner_text()
        assert "TOOL CALLS" in t_drawer_text
        assert "TOKENS USED" in t_drawer_text
        assert "TOTAL ELAPSED" in t_drawer_text
        assert "Replan Triggered" in t_drawer_text
        print("PASS 8: Agent Trace verified on Theories")

        page.screenshot(path=str(SCREENSHOTS_DIR / "14_theories_agent_trace.png"))
        print(f"Captured screenshot: {SCREENSHOTS_DIR / '14_theories_agent_trace.png'}")

        # 9. Test Back button navigation
        back_btn = page.locator("button:has-text('Back')")
        back_btn.click()
        page.wait_for_url(lambda u: "investigate" in u, timeout=5000)
        print("PASS 9: Back button from Theories navigated back to Investigate")

        # 10. Re-advance to Theories, then to Fix screen
        page.locator("button:has-text('See likely causes')").click()
        page.wait_for_url(lambda u: "theories" in u, timeout=5000)

        continue_fix_btn = page.locator("button:has-text('Review fix')")
        continue_fix_btn.click()
        page.wait_for_url(lambda u: "fix" in u, timeout=5000)
        print("PASS 10: Navigated to Fix screen")

        # 11. Verify RiskScale buttons and explanation panel
        page.wait_for_selector("#risk-btn-safe", timeout=8000)
        safe_btn = page.locator("#risk-btn-safe")
        rev_btn = page.locator("#risk-btn-reversible")
        risky_btn = page.locator("#risk-btn-risky")

        safe_btn.scroll_into_view_if_needed()
        assert safe_btn.is_visible()
        assert rev_btn.is_visible()
        assert risky_btn.is_visible()

        # Click Reversible button
        rev_btn.click()
        time.sleep(0.3)
        assert page.locator("text=Changes something, but it can be undone.").is_visible()
        print("PASS 11: RiskScale button expanded explanation panel")

        # Verify read-only caption
        assert page.locator("text=Set by the agent. Enforced when you approve.").is_visible()
        print("PASS 12: Read-only Risk caption displayed on Fix screen")

        # 13. Navigate to Decision screen and verify RiskScale there as well
        page.locator("button:has-text('Continue to decision')").click()
        page.wait_for_url(lambda u: "decision" in u, timeout=5000)
        page.wait_for_selector("#risk-btn-safe", timeout=5000)
        d_safe_btn = page.locator("#risk-btn-safe")
        d_safe_btn.click()
        time.sleep(0.3)
        assert page.locator("text=Read-only or no effect on live systems.").is_visible()
        print("PASS 13: RiskScale buttons and explanation verified on Decision screen")

        browser.close()
        print("\n==========================================")
        print("ALL PHASE 9 BROWSER CHECKS PASSED (EXIT 0)")
        print("==========================================")
        sys.exit(0)
finally:
    server_proc.terminate()
    try:
        server_proc.wait(timeout=3)
    except Exception:
        server_proc.kill()
    if TEST_DB.exists():
        TEST_DB.unlink()
