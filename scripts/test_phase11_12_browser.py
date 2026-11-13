#!/usr/bin/env python3
"""
Phase 11 & 12 Browser Verification Script

Tests:
  Phase 11:
    - Untrusted instruction blocked notice on Investigate screen
    - Untrusted notice in Agent Trace drawer
    - Audit log screen: table, filters, row expansion
    - Non-admin user: audit nav hidden, 403 forbidden state
  Phase 12:
    - Theories screen: Code change tab with colored monospace diff
    - Incident memory: record outcome on Success screen, saved to team memory
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
TEST_DB = Path("/tmp/e2e_phase11_12_test.db")
TEST_PORT = 8200
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

if TEST_DB.exists():
    TEST_DB.unlink()

sys.path.insert(0, str(AGENTX_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AGENT_MODE"] = "mock"
os.environ["SECRET_KEY"] = "e2e-browser-p11-12-secret-key-at-least-32-chars!"
os.environ["PRODUCTION"] = "false"
os.environ["ANTHROPIC_API_KEY"] = "mock-key-not-used"

from app.database import init_db, create_user
from app.auth import hash_password

init_db()
create_user("admin", hash_password("AdminPass1234!"), role="admin")
create_user("engineer", hash_password("EngineerPass123!"), role="user")

env = os.environ.copy()
env["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
env["AGENT_MODE"] = "mock"
env["SECRET_KEY"] = "e2e-browser-p11-12-secret-key-at-least-32-chars!"
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

# Poll until server is ready
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

        def screenshot(name: str):
            path = SCREENSHOTS_DIR / name
            page.screenshot(path=str(path))
            return str(path)

        def login(username, password):
            page.goto(f"{BASE_URL}/login")
            page.wait_for_selector('input[type="text"]')
            page.fill('input[type="text"]', username)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_url(lambda u: "alert" in u, timeout=10_000)

        # ── PART 1: Phase 11 — Injection Notice on Investigate & in Trace ──
        print("\n=== Phase 11: Prompt Injection Notice & Trace ===")
        login("admin", "AdminPass1234!")

        # Trigger bad_deploy_slow_queries (contains injection in logs)
        page.wait_for_selector("select")
        page.select_option("select", "bad_deploy_slow_queries")
        time.sleep(0.3)
        page.click("button:has-text('Start investigation')")

        # Wait for investigation completion
        page.wait_for_selector("text=Checks complete. Review the findings", timeout=20_000)
        check("11.1 Investigation completed on bad_deploy_slow_queries", True)

        # Verify untrusted instruction blocked notice appeared on Investigate
        notice = page.locator("[data-testid='untrusted-instruction-notice']")
        notice_visible = notice.is_visible()
        check("11.2 Untrusted instruction notice rendered on Investigate", notice_visible)
        screenshot("21_untrusted_instruction_notice.png")

        # Open trace drawer and check for trace notice
        page.click("button:has-text('Agent Trace')")
        time.sleep(0.4)
        trace_notice = page.locator("[data-testid='trace-untrusted-notice']")
        check("11.3 Untrusted instruction notice in trace drawer", trace_notice.is_visible())
        screenshot("22_trace_untrusted_notice.png")

        # ── PART 2: Phase 11 — Audit Log UI ──────────────────────────────
        print("\n=== Phase 11: Audit Log UI (Admin) ===")
        # Open user menu (desktop bar)
        page.locator("header button[aria-label='Open user menu']").click()
        time.sleep(0.3)
        # Check audit log nav item exists for admin
        admin_audit_item = page.locator("[data-testid='nav-audit-log']")
        check("11.4 Audit log nav item visible for admin", admin_audit_item.is_visible())

        # Click audit log
        admin_audit_item.click()
        page.wait_for_url(lambda u: "audit" in u, timeout=8_000)
        check("11.5 Navigated to Audit Log screen", True)

        # Table loaded with records
        page.wait_for_selector("table tbody tr", timeout=8_000)
        row_count = page.locator("table tbody tr").count()
        check("11.6 Audit log table has rows", row_count > 0, f"rows={row_count}")
        screenshot("23_audit_log_table.png")

        # Filter by search
        page.fill("[data-testid='audit-search-filter']", "untrusted")
        time.sleep(0.4)
        filtered_rows = page.locator("table tbody tr").count()
        check("11.7 Search filter narrows audit rows", filtered_rows > 0)

        # Clear search filter
        page.click("button:has-text('Clear')")
        time.sleep(0.3)

        # Expand a row
        page.locator("table tbody tr").first.click()
        time.sleep(0.3)
        check("11.8 Expanded audit row details visible", page.locator("text=Close").is_visible())
        screenshot("24_audit_log_expanded.png")

        # ── PART 3: Phase 11 — Non-admin Forbidden & Nav Hidden ────────────
        print("\n=== Phase 11: Non-admin Access Control ===")
        # Logout
        page.locator("header button[aria-label='Open user menu']").click()
        time.sleep(0.3)
        page.click("text=Sign out")
        page.wait_for_url(lambda u: "login" in u, timeout=8_000)

        # Login as non-admin engineer
        login("engineer", "EngineerPass123!")

        # Open user menu: audit nav MUST be hidden
        page.locator("header button[aria-label='Open user menu']").click()
        time.sleep(0.3)
        non_admin_audit_item = page.locator("[data-testid='nav-audit-log']").count()
        check("11.9 Audit log nav item hidden for non-admin", non_admin_audit_item == 0)

        # Direct navigation to #audit should show forbidden state
        page.goto(f"{BASE_URL}/#audit")
        page.wait_for_selector("[data-testid='audit-forbidden-state']", timeout=8_000)
        check("11.10 Non-admin direct access shows 403 Access Denied state", True)
        screenshot("25_audit_forbidden_state.png")

        # ── PART 4: Phase 12 — Code Change Tab on Theories ─────────────────
        print("\n=== Phase 12: Code Change Diff View on Theories ===")
        # Logout engineer, log back in as admin
        page.goto(f"{BASE_URL}/login")
        login("admin", "AdminPass1234!")

        # Run investigation on bad_deploy_slow_queries
        page.wait_for_selector("select")
        page.select_option("select", "bad_deploy_slow_queries")
        time.sleep(0.3)
        page.click("button:has-text('Start investigation')")
        page.wait_for_selector("text=Checks complete. Review the findings", timeout=20_000)

        # Go to Theories
        page.click("button:has-text('See likely causes')")
        page.wait_for_url(lambda u: "theories" in u, timeout=8_000)
        check("12.1 Arrived at Theories screen", True)

        # Open theory 1 (already open or click it)
        # Check for 'Code change' tab button
        page.wait_for_selector("[data-testid='tab-code-change']", timeout=8_000)
        code_tab_btn = page.locator("[data-testid='tab-code-change']").first
        check("12.2 'Code change' tab button visible", code_tab_btn.is_visible())

        # Click Code change tab
        code_tab_btn.click()
        time.sleep(0.4)
        # Verify CodeDiffViewer is rendered
        diff_viewer = page.locator("[data-testid='code-diff-viewer']").first
        check("12.3 Code diff viewer rendered", diff_viewer.is_visible())
        diff_text = diff_viewer.inner_text()
        check("12.4 Diff contains additions (+) and deletions (-)", "+" in diff_text and "-" in diff_text)
        screenshot("26_code_diff_tab.png")

        # ── PART 5: Phase 12 — Incident Memory on Decision & Success ──────
        print("\n=== Phase 12: Incident Memory Recording ===")
        # Navigate through fix to decision
        page.click("button:has-text('Review fix')")
        page.wait_for_url(lambda u: "fix" in u, timeout=8_000)
        page.click("button:has-text('Continue to decision')")
        page.wait_for_url(lambda u: "decision" in u, timeout=8_000)

        # Approve fix (Level 1)
        page.click("button:has-text('Approve fix')")
        page.wait_for_url(lambda u: "success" in u, timeout=8_000)
        check("12.5 Arrived at Success screen", True)

        # Record outcome card is visible
        outcome_card = page.locator("[data-testid='record-outcome-card']")
        check("12.6 Record outcome card rendered on Success screen", outcome_card.is_visible())

        # Fill note and save
        page.fill("[data-testid='outcome-note-input']", "Index restored; query time dropped to 12ms")
        time.sleep(0.2)
        page.click("[data-testid='save-outcome-btn']")

        # Banner should appear
        page.wait_for_selector("[data-testid='outcome-saved-banner']", timeout=8_000)
        check("12.7 Outcome saved banner confirmed", True)
        screenshot("27_incident_memory_saved.png")

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
print("Phase 11 & 12 Browser Test Results")
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
