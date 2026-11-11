# OnCall Rehearsal Agent — SPEC

Status: FINALIZED

## Pitch Line
"The on-call agent that rehearses the fix before you run it."

## Goal
An AI on-call incident agent. When a simulated production alert fires, the agent investigates using tools (recent deploys, logs, metrics, past incidents), returns three ranked hypotheses with evidence for and against, proposes a fix, rehearses that fix in a simulated sandbox showing before/after metrics, and then waits for a human to approve. Nothing is applied without human approval.

## Tech Stack
- Backend: Python 3.11+, FastAPI, Uvicorn, Pydantic (strict validation)
- LLM: Anthropic Python SDK with tool use. Model from env CLAUDE_MODEL (default "claude-sonnet-5-5"). API key from env ANTHROPIC_API_KEY.
- Frontend: plain HTML/CSS/JS, no build step, served by FastAPI. Stream via SSE. No external CDN. SVG charts.
- Storage: SQLite for users, sessions, investigations, audit log. Scenario data in files.

## Scenarios
- bad_deploy_slow_queries
- connection_pool_leak
- memory_leak

Each: ~80% routine log noise + 2 misleading red herrings.

## Agent Tools (12 tool call cap per investigation)
- get_recent_deploys(service, hours)
- query_logs(service, minutes, level, keyword)
- get_metrics(service, metric, minutes)
- search_past_incidents(query)
- run_in_sandbox(fix_id)

## Agent Output (Pydantic validated, retry once if invalid)
- hypotheses: exactly 3 items {rank, cause, confidence 0-1, evidence_for[], evidence_against[]}
- proposed_fix: {fix_id, action, risk_level 0-2, blast_radius, rationale}
- Each evidence item cites tool call + source row

## Risk Ladder (enforced in backend code)
- Level 0: auto-run (read-only + sandbox)
- Level 1: one-click approval
- Level 2: type "CONFIRM <fix_id>" + blast-radius preview

## UI
1. Alert panel: choose scenario, "Trigger alert"
2. Live investigation: tool calls streamed via SSE
3. Hypothesis court: 3 cards with expandable evidence
4. Rehearsal: before/after metrics + SVG chart
5. Approval bar: Approve/Reject + Level 2 typed confirmation
6. Stopwatch demo mode: Manual vs Agent
7. Audit log page (admin only)
8. Login page

## Security Requirements
1. Secrets from env only, never in code/logs/browser
2. Startup validation prints SET/MISSING without values
3. Auth: argon2 hashing, HttpOnly+Secure+SameSite cookies, CSRF, session expiry, brute-force lockout
4. Authorization: server-side role checks, IDOR prevention
5. Input: Pydantic strict, allowlists for scenario_id/fix_id, textContent not innerHTML
6. Rate limiting: per-IP login lockout, agent 5/min, global 100/min/IP
7. CORS: own origin only, 1MB request limit, generic errors
8. Debug off in prod, /docs disabled in prod
9. Security headers: CSP, XCTO, XFO, Referrer-Policy, Permissions-Policy, HSTS
10. Pinned deps, pip-audit, no dead code
11. Only /static served over HTTP
12. SQLite outside static, parameterized only, 0o640 permissions
13. Git hygiene: gitleaks/trufflehog scan
14. Prompt injection: delimiters, system prompt warning, test
15. SECURITY_AUDIT.md

## Build Phases
- Phase 1: skeleton, auth, security baseline, data loader, sample data ← CURRENT
- Phase 2: tools, agent loop for scenario 1, pytest tests
- Phase 3: hypothesis court UI, scenarios 2 and 3
- Phase 4: sandbox rehearsal, risk ladder, approval flow, audit log
- Phase 5: evaluation script, prompt-injection test, stopwatch mode
- Phase 6: full security audit, README
