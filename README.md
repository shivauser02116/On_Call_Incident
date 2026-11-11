# OnCall Rehearsal Agent

> *"The on-call agent that rehearses the fix before you run it."*

An AI-powered on-call incident response agent built for production safety. When a simulated production alert fires, the agent investigates using read-only telemetry tools (recent deploys, logs, metrics, past incidents), synthesizes three ranked hypotheses in a cross-examined "Hypothesis Court" with empirical evidence, proposes a fix, **rehearses that fix in an isolated simulation sandbox showing before/after metrics and impact charts**, and then halts for human approval.

**Zero actions are executed in production without explicit human authorization.**

---

## ⚡ Quickstart (Run in 5 Commands)

```bash
# 1. Enter project directory
cd AgentX

# 2. Create and activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install pinned dependencies
pip install -r requirements.txt

# 4. Configure environment and create admin user (prompts securely for password)
cp .env.example .env && python3 create_admin.py

# 5. Start the production-hardened web application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open your browser at **http://localhost:8000** and sign in with the admin credentials you just created.

---

## 🏗️ Architecture & Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2 (strict validation).
- **LLM**: Anthropic Python SDK with function/tool use (`claude-sonnet-5-5` default). Read-only investigation cap at 12 tool calls.
- **Frontend**: Plain HTML5/CSS3/JavaScript — **Zero build step, zero external CDN scripts**.
- **Real-Time Streaming**: Server-Sent Events (SSE) streaming live investigation steps and tool call outputs.
- **Data Visualization**: Pure inline SVG charts dynamically rendered client-side (no charting library dependencies).
- **Storage**: SQLite (`chmod 0o640`) with parameterized queries for users, sessions, investigations, and immutable audit logs.
- **Simulation**: Telemetry and sandbox rehearsal effects driven by static incident scenario files.

---

## 🚨 Incident Scenarios

All scenarios feature ~80% routine operational log noise and 2 realistic red herrings:

| Scenario ID | Incident Alert | Genuine Root Cause | Red Herrings | Correct Fix & Risk |
|---|---|---|---|---|
| `bad_deploy_slow_queries` | P95 Latency 9200ms SLO Breach | Deploy removed index on `orders.status` causing full table scans | Elasticsearch yellow maintenance status; Redis eviction policy | `fix_add_index` (Risk Level 1: Reversible) |
| `connection_pool_leak` | DB Connection Pool 100/100 Exhausted | DB session middleware refactor removed context manager `with` blocks and omitted `finally` session close | Segment analytics timeout; 45-day cert expiry warning | `fix_restart_app` (Risk Level 1: Reversible) |
| `memory_leak` | OOMKiller Activated, Memory 97% | Request logging middleware accumulating payloads in unbounded module list `request_body_log` | High GC pause times; Customer webhook delivery timeout | `fix_patch_middleware` (Risk Level 1: Reversible) |

---

## 🛠️ The 5 Agent Tools

The agent operates in a strictly read-only sandbox with zero execution capabilities:

1. `get_recent_deploys(service, hours)`: Queries recent software releases, commit messages, and diff summaries.
2. `query_logs(service, minutes, level, keyword)`: Inspects application, database, and system logs.
3. `get_metrics(service, metric, minutes)`: Queries timeseries metrics (`p95_latency_ms`, `error_rate_pct`, `memory_mb`, `db_connections`).
4. `search_past_incidents(query)`: Performs keyword scoring over 20 historical post-mortem incident reports.
5. `run_in_sandbox(fix_id)`: Rehearses the remediation in an isolated simulation sandbox, returning simulated before/after telemetry.

---

## 🪜 The Risk Ladder

Enforced strictly in backend code (`app/routes/api_routes.py`), never reliant on prompt instructions alone:

- **Level 0 (Safe / Read-Only)**: Read-only telemetry investigation and sandbox simulation run automatically with zero mutation.
- **Level 1 (Reversible Fix)**: Requires authenticated human one-click approval via `POST /api/investigations/{id}/approve` with valid session cookie and CSRF token.
- **Level 2 (Destructive Fix)**: Requires user to type the exact confirmation phrase `CONFIRM <fix_id>` along with a blast-radius preview.
- **LLM Boundary**: The agent has no access to approval endpoints or mutation tools. Only human operators can approve fixes.

---

## ⏱️ Stopwatch Demo Mode

Demonstrates the dramatic efficiency leap of agentic on-call triage:

- **Manual Mode**: Live stopwatch timer while the engineer manually searches and filters raw logs in the built-in terminal viewer.
- **Agent Mode**: Real-time timer measuring automated investigation, hypothesis cross-examination, and sandbox rehearsal (~4-6 seconds vs. ~35 minutes manual triage).

---

## 🧪 Testing & Verification

Run the full automated test suite (130 tests covering auth, security headers, IDOR, path traversal, risk ladder, and prompt injection):

```bash
python3 -m pytest -v
```

Run the empirical evaluation harness (evaluates all scenarios 5 times against canonical `answer_key.txt`):

```bash
python scripts/evaluate.py --runs 5
```

Run the git secret scanner and pre-commit validator:

```bash
python scripts/secret_scan.py
```
