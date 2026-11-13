#!/usr/bin/env python3
"""
Phase 9 Browser Verification Script
Tests Plan checklist, Replan event notice, and Agent Trace drawer on Investigate and Theories.
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
TEST_PORT = 8196
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
        print("PASS 2: Triggered ambiguous_escalate investigation")

        # 3. Check for Investigation Plan checklist
        page.wait_for_selector("text=Investigation Plan", timeout=6000)
        print("PASS 3: Investigation Plan checklist rendered on Investigate screen")

        # 4. Wait for investigation to progress & check for Replan notice or completed status
        time.sleep(1.0)
        trace_button = page.locator("button:has-text('Agent Trace')")
        trace_button.wait_for(state="visible", timeout=5000)
        trace_button.click()
        print("PASS 4: Agent Trace drawer expanded on Investigate screen")

        page.screenshot(path=str(SCREENSHOTS_DIR / "13_investigate_plan_and_trace.png"))
        print(f"Captured screenshot: {SCREENSHOTS_DIR / '13_investigate_plan_and_trace.png'}")

        # 5. Wait for transition to Theories
        page.wait_for_url(lambda u: "theories" in u, timeout=10000)
        print("PASS 5: Investigation completed and auto-navigated to Theories")

        # 6. Verify Agent Trace drawer on Theories
        theories_trace_button = page.locator("button:has-text('Agent Trace')")
        theories_trace_button.wait_for(state="visible", timeout=5000)
        theories_trace_button.scroll_into_view_if_needed()
        theories_trace_button.click()
        time.sleep(0.5)

        drawer = page.locator(".bg-bg\\/40")
        drawer.wait_for(state="visible", timeout=5000)
        drawer_text = drawer.inner_text()

        assert "TOOL CALLS" in drawer_text
        assert "TOKENS USED" in drawer_text
        assert "TOTAL ELAPSED" in drawer_text
        assert "Replan Triggered" in drawer_text
        assert "get_metrics" in drawer_text
        assert "query_logs" in drawer_text
        assert "run_in_sandbox" in drawer_text
        print("PASS 6: Agent Trace metrics (tool calls, tokens, elapsed, replan notice) verified on Theories")
        print("PASS 7: Individual tool execution trace steps verified inside drawer on Theories")

        page.screenshot(path=str(SCREENSHOTS_DIR / "14_theories_agent_trace.png"))
        print(f"Captured screenshot: {SCREENSHOTS_DIR / '14_theories_agent_trace.png'}")

        browser.close()
        print("\nALL PHASE 9 BROWSER CHECKS PASSED!")
finally:
    server_proc.terminate()
    try:
        server_proc.wait(timeout=3)
    except Exception:
        server_proc.kill()
    if TEST_DB.exists():
        TEST_DB.unlink()
