# OnCall Rehearsal Agent

> *"The on-call agent that rehearses the fix before you run it."*

An AI-powered on-call incident response agent built for production safety. When a simulated production alert fires, the agent investigates using read-only telemetry tools (recent deploys, logs, metrics, past incidents), synthesizes three ranked hypotheses in a cross-examined "Hypothesis Court" with empirical evidence, proposes a fix, **rehearses that fix in an isolated simulation sandbox showing before/after metrics and impact charts**, and then halts for human approval.

**Zero actions are executed in production without explicit human authorization.**

---

## ⚡ Local Setup & Run Guide

Here are exact, copy-paste commands to set up, build, and run the complete application locally.

### 1. Install Backend Dependencies

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install pinned Python dependencies
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies & Build UI

```bash
# Enable corepack (bundled with Node 20+) to use pnpm without global install
corepack enable

# Install frontend dependencies
corepack pnpm --dir frontend install

# Build production static bundle to frontend/dist
corepack pnpm --dir frontend build
```

*(Alternatively, `cd frontend && pnpm install && pnpm build && cd ..`)*

### 3. Create the Admin User

```bash
# Interactively creates the initial admin user in SQLite (prompts for username & password)
python3 create_admin.py
```

### 4. Run the Server

#### Option A: Mock Mode (Zero API spend — deterministic simulation)
```bash
AGENT_MODE=mock uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### Option B: Live Mode (Real Claude API)
```bash
# Set your Anthropic API key in environment or in .env
export ANTHROPIC_API_KEY="sk-ant-..."
export SECRET_KEY="your-32-plus-character-secret-key-goes-here"

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

*(You can also place `ANTHROPIC_API_KEY` and `SECRET_KEY` into a local `.env` file — the app loads it automatically).*

#### Verifying Active Mode at Startup
The application explicitly logs its active agent mode on startup:
```text
INFO:     Agent mode: MOCK (model: N/A (mock))
# or
INFO:     Agent mode: LIVE (model: claude-sonnet-5-5)
```

Open your browser at **http://127.0.0.1:8000** and log in with the admin credentials you created.

---

## 🧪 Running Tests & Evaluation

### Run Full Pytest Suite (174 tests)
```bash
pytest tests -v
```

### Run Evaluation Harness Across All 6 Scenarios
```bash
# In mock mode (30 runs, deterministic validation):
AGENT_MODE=mock python scripts/evaluate.py --runs 5

# In live Claude API mode:
python scripts/evaluate.py --runs 5
```

### Run Secret Scanner
```bash
python scripts/secret_scan.py
```

### Run Scenario Validator (for new scenario contributions)
```bash
python scripts/validate_scenario.py data/scenarios/bad_deploy_slow_queries
```

---

## 🏗️ Architecture & Tech Stack

- **Backend**: Python 3.12+, FastAPI, Starlette, Uvicorn, Pydantic v2 (strict validation).
- **LLM**: Anthropic Claude API (`claude-sonnet-5-5` default) with tool calling and strict Pydantic output validation. Read-only investigation cap at 12 tool calls.
- **Agent Modes**:
  - `live`: Uses real Anthropic API via `CLAUDE_MODEL` and `ANTHROPIC_API_KEY`. No silent fallback to simulation.
  - `mock`: Uses deterministic scenario telemetry simulation. Activated only when `AGENT_MODE=mock` is explicitly configured.
- **Frontend**: React 19, TypeScript, Tailwind CSS v4, built to static files with Vite. Single-page hash routing, Server-Sent Events (SSE) streaming reader, inline SVG telemetry charts. Zero external CDNs, zero remote fonts, zero inline scripts.
- **Security & Storage**: SQLite (`chmod 0o640`) with parameterized SQL, Argon2id password hashing, `HttpOnly` / `SameSite=Strict` session cookies, double-submit CSRF cookie validation, slowapi rate limiting.
- **Containerization**: Multi-stage Dockerfile (non-root `appuser`, healthcheck, zero baked-in secrets). Cloud Run deployment ready (`DEPLOY.md`).

---

## 🚨 Incident Scenarios

All scenarios feature ~80% routine operational log noise and realistic red herrings:

| Scenario ID | Incident Alert | Genuine Root Cause | Red Herrings | Correct Fix & Risk | Log Format |
|---|---|---|---|---|---|
| `bad_deploy_slow_queries` | P95 Latency 9200ms SLO Breach | Deploy removed index on `orders.status` causing full table scans | Elasticsearch yellow maintenance status; Redis eviction policy | `fix_add_index` (Risk Level 1: Reversible) | Python tracebacks / SQL |
| `connection_pool_leak` | DB Connection Pool 100/100 Exhausted | DB session middleware refactor removed context manager `with` blocks and omitted `finally` session close | Segment analytics timeout; 45-day cert expiry warning | `fix_restart_app` (Risk Level 1: Reversible) | Python tracebacks |
| `memory_leak` | OOMKiller Activated, Memory 97% | Request logging middleware accumulating payloads in unbounded module list `request_body_log` | High GC pause times; Customer webhook delivery timeout | `fix_patch_middleware` (Risk Level 1: Reversible) | Python tracebacks / GC |
| `third_party_outage` | PayFlow Upstream Outage (HTTP 504) | Third-party payment gateway outage causing un-jittered retry storm that saturated worker threads | Promo banner frontend deploy commit 48f91 (alice); database connection spike | `fix_enable_circuit_breaker` (Risk Level 1: Reversible) | Java exceptions (`java.net.SocketTimeoutException`) |
| `config_change_flag` | DB Query Timeouts Surging to 94% | Dynamic config key `db_pool_timeout_ms` set to 50ms via Consul KV; zero code deployments | Node.js event loop starvation; routine scheduled DB backup | `fix_revert_config_flag` (Risk Level 0: Safe) | Node.js / Knex stack traces (`TimeoutError`) |
| `ambiguous_escalate` | Erratic Latency Jitter (120ms - 4500ms) | Conflicting multi-system signals: AZ transit gateway TCP RST drops + cloud provider edge DNS timeouts; confidence < 0.40 | Worker node 4 CPU throttling burst; Redis cache miss rate increase | `fix_escalate_human_operator` (Risk Level 0: Safe) | Mixed Python tracebacks & socket.gaierror |

---

## 🛠️ The 5 Agent Tools

The agent operates in a strictly read-only sandbox with zero mutation capabilities:

1. `get_recent_deploys(service, hours)`: Queries recent software releases, commit messages, and diff summaries.
2. `query_logs(service, minutes, level, keyword)`: Inspects application, database, and system logs.
3. `get_metrics(service, metric, minutes)`: Queries timeseries metrics (`p95_latency_ms`, `error_rate_pct`, `memory_mb`, `db_connections`).
4. `search_past_incidents(query)`: Performs keyword scoring over historical post-mortem incident reports in `past_incidents.csv`.
5. `run_in_sandbox(fix_id)`: Rehearses the remediation in an isolated simulation sandbox, returning simulated before/after telemetry.

---

## 🪜 The Risk Ladder

Enforced strictly in backend code (`app/routes/api_routes.py`), never reliant on prompt instructions alone:

- **Level 0 (Safe / Read-Only)**: Read-only telemetry investigation and sandbox simulation run automatically with zero mutation.
- **Level 1 (Reversible Fix)**: Requires authenticated human one-click approval via `POST /api/investigations/{id}/approve` with valid session cookie and CSRF token.
- **Level 2 (Destructive Fix)**: Requires user to type the exact confirmation phrase `CONFIRM <fix_id>` along with a blast-radius preview.
- **LLM Boundary**: The agent has no access to approval endpoints or mutation tools. Only human operators can approve fixes.
