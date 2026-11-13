#!/usr/bin/env python3
"""Generate sample data for all 3 scenarios."""
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
NOW = datetime.now(timezone.utc)


def ts(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# PAST INCIDENTS
# ══════════════════════════════════════════════════════════════════════════════
past_incidents = [
    {"id": "INC-001", "symptoms": "high latency slow queries database timeout", "root_cause": "Missing index on users.email column after migration", "fix": "CREATE INDEX idx_users_email ON users(email)"},
    {"id": "INC-002", "symptoms": "connection pool exhausted timeout all connections used", "root_cause": "Database connections leaked in background job — missing finally block", "fix": "Added finally block to background job connection handler"},
    {"id": "INC-003", "symptoms": "memory usage climbing OOM process killed restart loop", "root_cause": "In-memory cache growing unbounded — no TTL set", "fix": "Set cache TTL to 300s and max size to 10000 entries"},
    {"id": "INC-004", "symptoms": "high error rate 502 bad gateway upstream timeout", "root_cause": "Upstream service deployed broken TLS certificate", "fix": "Rolled back upstream deployment, renewed certificate"},
    {"id": "INC-005", "symptoms": "slow queries full table scan orders table", "root_cause": "deploy removed index on orders.status during schema migration", "fix": "Re-added index CREATE INDEX idx_orders_status ON orders(status)"},
    {"id": "INC-006", "symptoms": "connection pool leak connections not released growing", "root_cause": "Context manager removed from session middleware in refactor", "fix": "Restored context manager pattern in database session middleware"},
    {"id": "INC-007", "symptoms": "memory leak request objects accumulating logging", "root_cause": "Debug logging middleware storing full request bodies in module-level list", "fix": "Removed request body accumulation from logging middleware"},
    {"id": "INC-008", "symptoms": "high cpu load nginx worker oom killer", "root_cause": "Regex catastrophic backtracking in input validation", "fix": "Replaced with linear-time regex or non-regex validation"},
    {"id": "INC-009", "symptoms": "database slow checkpoint wal file growing", "root_cause": "WAL mode checkpoint not running due to misconfigured auto-checkpoint threshold", "fix": "Set PRAGMA wal_autocheckpoint=1000 and ran PRAGMA wal_checkpoint(TRUNCATE)"},
    {"id": "INC-010", "symptoms": "api timeout downstream service 503 retry storm", "root_cause": "Missing circuit breaker caused retry storm on downstream failure", "fix": "Implemented circuit breaker with 30s open window"},
    {"id": "INC-011", "symptoms": "disk io high 100% iops saturation latency spike", "root_cause": "Log rotation not configured — single log file reached 50GB", "fix": "Configured logrotate with daily rotation and 7-day retention"},
    {"id": "INC-012", "symptoms": "slow queries missing index n+1 query problem", "root_cause": "ORM lazy loading generating N+1 queries on user list endpoint", "fix": "Added eager loading with joinedload() for related models"},
    {"id": "INC-013", "symptoms": "connection refused redis unavailable eviction", "root_cause": "Redis maxmemory reached and evicted active session keys", "fix": "Increased Redis maxmemory-policy to volatile-lru, added alerts"},
    {"id": "INC-014", "symptoms": "high memory python gc pause objects not freed", "root_cause": "Circular reference between objects preventing garbage collection", "fix": "Used weakref.WeakValueDictionary for cache to allow GC"},
    {"id": "INC-015", "symptoms": "deploy rollback slow queries performance regression", "root_cause": "New feature added missing composite index", "fix": "Added composite index on (tenant_id, created_at) columns"},
    {"id": "INC-016", "symptoms": "connection timeout postgresql max_connections hit", "root_cause": "pgBouncer pool size increased without increasing PostgreSQL max_connections", "fix": "Increased max_connections to 500 and pg_hba reload"},
    {"id": "INC-017", "symptoms": "api errors 500 null pointer exception uncaught", "root_cause": "deploy removed null check in user profile handler", "fix": "Reverted commit, added null guard with safe default value"},
    {"id": "INC-018", "symptoms": "memory growing heap dump large string objects", "root_cause": "Response caching caching unbounded large payloads", "fix": "Added max payload size limit of 1MB to response cache"},
    {"id": "INC-019", "symptoms": "database deadlock concurrent updates same row lock wait", "root_cause": "Two background jobs updating same resource without consistent lock ordering", "fix": "Sorted lock acquisition order alphabetically by resource ID"},
    {"id": "INC-020", "symptoms": "cpu spike background job runaway loop", "root_cause": "Job scheduler retry backoff not implemented — tight loop on failure", "fix": "Added exponential backoff with jitter and max retries=5"},
]
write_csv(DATA / "past_incidents.csv", past_incidents,
          ["id", "symptoms", "root_cause", "fix"])


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1: bad_deploy_slow_queries
# ══════════════════════════════════════════════════════════════════════════════
S1 = DATA / "scenarios" / "bad_deploy_slow_queries"

# Deploy at t=-35min caused the incident
deploy_time_s1 = (NOW - timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")

logs_s1 = []
# Routine noise — before the bad deploy (t=-120 to t=-40)
routine_before = [
    ("INFO",  "Application started successfully"),
    ("DEBUG", "Health check ping from load balancer"),
    ("INFO",  "GET /api/users 200 42ms"),
    ("INFO",  "GET /api/products 200 38ms"),
    ("DEBUG", "Redis cache hit for key user:session:abc123"),
    ("INFO",  "POST /api/orders 201 95ms"),
    ("DEBUG", "Background job: cleanup expired sessions — 0 deleted"),
    ("INFO",  "GET /api/health 200 2ms"),
    ("DEBUG", "Metrics scraped by Prometheus"),
    ("INFO",  "Worker queue depth: 3 tasks"),
    ("INFO",  "GET /api/orders/list 200 65ms"),
    ("DEBUG", "Cache miss for product:catalog:v2 — fetching from DB"),
    ("INFO",  "POST /api/payments 201 220ms"),
    ("INFO",  "GET /api/users/profile 200 44ms"),
    ("DEBUG", "Celery task send_email queued successfully"),
    ("INFO",  "PUT /api/orders/789 200 78ms"),
    ("DEBUG", "Connection pool: 8/100 connections in use"),
    ("INFO",  "GET /api/analytics/daily 200 180ms"),
    ("DEBUG", "GC cycle completed in 12ms"),
    ("INFO",  "GET /api/search 200 95ms"),
]
# Red herring 1: Elasticsearch yellow status (unrelated maintenance)
# Red herring 2: Redis eviction (always configured this way)
red_herrings_s1 = [
    ("WARNING", "Elasticsearch cluster status: yellow (1 unassigned shard) — scheduled maintenance"),
    ("WARNING", "Elasticsearch index health check: yellow (replica not assigned)"),
    ("WARNING", "Redis eviction policy is allkeys-lru — this is expected configuration"),
    ("INFO",    "Elasticsearch snapshot completed: 2.3GB backed up"),
    ("WARNING", "Redis used_memory 68% of maxmemory — normal operating range"),
]
# Real signal — after bad deploy
signals_s1 = [
    ("WARNING", "Query execution time 8234ms exceeds threshold: SELECT * FROM orders WHERE status='pending'"),
    ("ERROR",   "Query execution time exceeded 30000ms on orders table — possible full table scan"),
    ("ERROR",   "SELECT * FROM orders WHERE status='pending' full table scan detected — no index on status column"),
    ("ERROR",   "Database connection pool 85/100 connections in use — approaching limit"),
    ("ERROR",   "Query timeout after 30s: SELECT COUNT(*) FROM orders WHERE status='pending' AND created_at > ?"),
    ("CRITICAL","Database connection pool exhausted: 100/100 connections in use — requests queuing"),
    ("ERROR",   "HTTP 503 returned to client — database unavailable after pool timeout"),
    ("ERROR",   "Query execution time exceeded 30000ms: UPDATE orders SET status='processing' WHERE status='pending'"),
    ("CRITICAL","Alert: p95 latency 8420ms (threshold: 500ms) — SLO breach"),
    ("ERROR",   "Database connection pool exhausted — dropping incoming requests"),
]

# Build log timeline
for i, (level, msg) in enumerate(routine_before * 4):
    logs_s1.append({"timestamp": ts(120 - i * 1.2), "level": level, "message": msg})

for i, (level, msg) in enumerate(red_herrings_s1 * 2):
    logs_s1.append({"timestamp": ts(90 - i * 8), "level": level, "message": msg})

for i, (level, msg) in enumerate(signals_s1):
    logs_s1.append({"timestamp": ts(34 - i * 2.5), "level": level, "message": msg})

# More routine noise mixed in
more_noise = [
    ("INFO",  "POST /api/users/register 201 112ms"),
    ("DEBUG", "Kafka consumer lag: 0 messages"),
    ("INFO",  "GET /api/config 200 15ms"),
    ("INFO",  "Scheduled report generated: daily_summary.pdf"),
    ("DEBUG", "JWT token validated for user admin@example.com"),
    ("INFO",  "PUT /api/settings 200 33ms"),
    ("INFO",  "GET /api/notifications 200 28ms"),
    ("DEBUG", "S3 presigned URL generated for upload"),
    ("INFO",  "DELETE /api/sessions/old 200 5ms"),
    ("INFO",  "Background metrics published to StatsD"),
]
for i, (level, msg) in enumerate(more_noise * 3):
    logs_s1.append({"timestamp": ts(55 - i * 0.8), "level": level, "message": msg})

logs_s1.sort(key=lambda r: r["timestamp"])
# Ensure exactly 150 rows
logs_s1 = logs_s1[:150]
write_csv(S1 / "logs.csv", logs_s1, ["timestamp", "level", "message"])

# Metrics: normal for 30 rows, then spike after deploy
metrics_s1 = []
for i in range(60):
    t = ts(60 - i)
    if i < 25:  # Normal
        metrics_s1.append({
            "timestamp": t, "p95_latency_ms": 185 + (i % 7) * 5,
            "error_rate_pct": 0.08 + (i % 3) * 0.02,
            "memory_mb": 510 + (i % 10) * 3,
            "db_connections": 8 + (i % 5),
        })
    elif i == 25:  # Deploy event
        metrics_s1.append({
            "timestamp": t, "p95_latency_ms": 2100,
            "error_rate_pct": 3.2, "memory_mb": 525, "db_connections": 45,
        })
    else:  # Spike
        factor = min(i - 25, 15)
        metrics_s1.append({
            "timestamp": t,
            "p95_latency_ms": min(2100 + factor * 450, 9200),
            "error_rate_pct": min(3.2 + factor * 0.9, 15.8),
            "memory_mb": 528 + factor * 2,
            "db_connections": min(45 + factor * 3, 100),
        })
write_csv(S1 / "metrics.csv", metrics_s1,
          ["timestamp", "p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"])

# Deploys
deploys_s1 = [
    {"time": ts(240), "author": "alice", "commit_message": "chore: update dependencies to latest stable versions", "files_changed": "requirements.txt", "diff_summary": "Bumped 12 packages, no logic changes"},
    {"time": ts(180), "author": "bob",   "commit_message": "feat: add user preferences API endpoint", "files_changed": "api/users.py, models/user.py", "diff_summary": "Added GET/PUT /api/users/preferences endpoint with validation"},
    {"time": ts(120), "author": "carol", "commit_message": "fix: correct email validation regex", "files_changed": "utils/validation.py", "diff_summary": "Fixed regex to handle plus-sign in email local part"},
    {"time": ts(90),  "author": "dave",  "commit_message": "docs: update API documentation for v2 endpoints", "files_changed": "docs/api.md", "diff_summary": "Updated 8 endpoint descriptions, added curl examples"},
    {"time": ts(35),  "author": "alice", "commit_message": "feat: add order status dashboard — optimize schema for reporting", "files_changed": "migrations/0042_order_dashboard.py, models/order.py, api/orders.py", "diff_summary": "Added order status view, removed index on orders.status column (believed redundant for dashboard query pattern), added orders_reporting view"},
]
write_csv(S1 / "deploys.csv", deploys_s1,
          ["time", "author", "commit_message", "files_changed", "diff_summary"])

sandbox_s1 = {
    "fix_add_index": {
        "description": "Re-add missing index on orders.status column: CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status)",
        "risk_level": 1,
        "blast_radius": "orders table locked for ~2 minutes during index creation; queries may queue but not fail",
        "after_metrics": {"p95_latency_ms": 185, "error_rate_pct": 0.08, "memory_mb": 522, "db_connections": 12},
    },
    "fix_rollback_deploy": {
        "description": "Full rollback of commit abc123 (order status dashboard feature) to previous stable state",
        "risk_level": 2,
        "blast_radius": "Full service restart (~30 seconds downtime); 2 hours of order dashboard work lost; any orders in-flight during restart may need reprocessing",
        "after_metrics": {"p95_latency_ms": 190, "error_rate_pct": 0.09, "memory_mb": 512, "db_connections": 11},
    },
}
write_json(S1 / "sandbox_effects.json", sandbox_s1)

write_text(S1 / "answer_key.txt", """root_cause: The deploy 35 minutes ago (alice, 'feat: add order status dashboard') removed the index on orders.status column, believing it was redundant for the new dashboard query pattern. This caused full table scans on all queries filtering by order status, exhausting the connection pool as queries took 30s+ instead of <10ms.

evidence: logs show 'full table scan detected — no index on status column' at t-34min; metrics show p95 latency spike from ~190ms to 9200ms exactly at deploy time (t-35min); deploys show 'removed index on orders.status column' in the diff_summary.

red_herrings:
  1. Elasticsearch yellow status — unrelated scheduled maintenance, pre-dates incident by >1 hour
  2. Redis eviction policy allkeys-lru — this is the always-on configuration, not a change

correct_fix: fix_add_index (risk_level 1) — re-add the index without full rollback
alternative: fix_rollback_deploy (risk_level 2) — works but destroys 2 hours of work unnecessarily
""")

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2: connection_pool_leak
# ══════════════════════════════════════════════════════════════════════════════
S2 = DATA / "scenarios" / "connection_pool_leak"

logs_s2 = []
routine_s2 = [
    ("INFO",  "GET /api/products 200 55ms"),
    ("DEBUG", "Cache lookup for product:sku:XJ-9000"),
    ("INFO",  "POST /api/checkout 201 180ms"),
    ("INFO",  "Worker heartbeat OK"),
    ("DEBUG", "Connection pool: {n}/100 connections in use"),
    ("INFO",  "GET /api/users/me 200 32ms"),
    ("DEBUG", "Background task: sync inventory — completed in 1.2s"),
    ("INFO",  "GET /api/orders/{id} 200 48ms"),
]
for i, (level, msg) in enumerate(routine_s2 * 10):
    logs_s2.append({"timestamp": ts(90 - i * 0.6), "level": level, "message": msg.replace("{n}", str(5 + i % 8)).replace("{id}", str(100 + i))})

# Red herring 1: external analytics service (unrelated)
# Red herring 2: certificate expiry warning (not causing incident)
red_herrings_s2 = [
    ("ERROR",   "Failed to send analytics event to Segment — network timeout (non-critical)"),
    ("WARNING", "Segment analytics delivery failed for event 'checkout_completed' — will retry"),
    ("WARNING", "TLS certificate for api.internal expires in 45 days — schedule renewal"),
    ("INFO",    "Segment batch delivered: 142 events"),
    ("WARNING", "Certificate expiry warning: metrics.internal cert expires 2026-12-26"),
]
for i, (level, msg) in enumerate(red_herrings_s2 * 3):
    logs_s2.append({"timestamp": ts(80 - i * 4), "level": level, "message": msg})

# Real signals — connection leak growing over time
signals_s2 = [
    ("WARNING", "Database session not released properly in /api/checkout handler — possible connection leak"),
    ("WARNING", "Connection pool: 35/100 connections in use — elevated (baseline 8)"),
    ("WARNING", "Connection pool: 52/100 connections in use — growing"),
    ("ERROR",   "Connection acquired but not released in background inventory sync task"),
    ("WARNING", "Connection pool: 71/100 connections in use — investigate"),
    ("ERROR",   "Pool timeout after 30s waiting for available connection — 1 request dropped"),
    ("WARNING", "Connection pool: 88/100 connections in use — critical threshold"),
    ("ERROR",   "Connection acquired but not released — context manager missing in db session middleware"),
    ("CRITICAL","All 100 connections in use — new requests queuing"),
    ("ERROR",   "Pool timeout after 30s waiting for connection — dropping request GET /api/orders"),
    ("CRITICAL","Connection pool exhausted — service degraded"),
]
for i, (level, msg) in enumerate(signals_s2):
    logs_s2.append({"timestamp": ts(50 - i * 3), "level": level, "message": msg})

logs_s2.sort(key=lambda r: r["timestamp"])
logs_s2 = logs_s2[:150]
write_csv(S2 / "logs.csv", logs_s2, ["timestamp", "level", "message"])

metrics_s2 = []
for i in range(60):
    t = ts(60 - i)
    conns = min(5 + i * 1.6, 100)
    error = max(0, (conns - 80) * 0.3)
    latency = 55 + max(0, (conns - 60) * 8)
    metrics_s2.append({
        "timestamp": t, "p95_latency_ms": round(latency),
        "error_rate_pct": round(error, 2),
        "memory_mb": 480 + i * 1.5,
        "db_connections": round(conns),
    })
write_csv(S2 / "metrics.csv", metrics_s2,
          ["timestamp", "p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"])

deploys_s2 = [
    {"time": ts(300), "author": "eve",   "commit_message": "feat: add product search with filters", "files_changed": "api/products.py, search/indexer.py", "diff_summary": "Added full-text search, filter by price/category"},
    {"time": ts(200), "author": "frank", "commit_message": "fix: correct pagination offset calculation", "files_changed": "utils/pagination.py", "diff_summary": "Fixed off-by-one error in cursor-based pagination"},
    {"time": ts(150), "author": "grace", "commit_message": "chore: upgrade SQLAlchemy to 2.0 compatibility", "files_changed": "requirements.txt, database/session.py", "diff_summary": "Updated session creation for SQLAlchemy 2.0 API"},
    {"time": ts(70),  "author": "henry", "commit_message": "refactor: extract database session management to middleware", "files_changed": "middleware/db_session.py, api/checkout.py, api/orders.py, api/products.py", "diff_summary": "Moved db session lifecycle from route handlers to middleware. Removed explicit 'with db.session() as session:' context manager blocks in handlers — session now injected by middleware. NOTE: middleware implementation missing finally block for session.close()"},
    {"time": ts(10),  "author": "grace", "commit_message": "docs: add middleware architecture diagram", "files_changed": "docs/architecture.md", "diff_summary": "Added sequence diagram for request lifecycle"},
]
write_csv(S2 / "deploys.csv", deploys_s2,
          ["time", "author", "commit_message", "files_changed", "diff_summary"])

sandbox_s2 = {
    "fix_connection_recycler": {
        "description": "Deploy connection recycler sidecar that forcefully closes idle connections held >60s (read-only monitoring tool)",
        "risk_level": 0,
        "blast_radius": "No service disruption — recycler runs alongside app, closes only idle leaked connections",
        "after_metrics": {"p95_latency_ms": 62, "error_rate_pct": 0.1, "memory_mb": 490, "db_connections": 15},
    },
    "fix_restart_app": {
        "description": "Graceful rolling restart of all app instances to clear leaked connections, then deploy hotfix with finally block",
        "risk_level": 1,
        "blast_radius": "~15 seconds of elevated latency during rolling restart; in-flight requests may retry; hotfix requires code review",
        "after_metrics": {"p95_latency_ms": 58, "error_rate_pct": 0.08, "memory_mb": 485, "db_connections": 8},
    },
}
write_json(S2 / "sandbox_effects.json", sandbox_s2)

write_text(S2 / "answer_key.txt", """root_cause: The deploy 70 minutes ago (henry, 'refactor: extract database session management to middleware') removed explicit context manager blocks ('with db.session() as session:') from route handlers and moved session lifecycle to middleware, but the middleware implementation is missing the finally block for session.close(). Every request acquires a database connection that is never released, causing the pool to fill up over ~45 minutes.

evidence: logs show 'Connection acquired but not released — context manager missing in db session middleware' and connections climbing from 8 to 100 over 45 minutes; deploys show 'Removed explicit context manager blocks ... missing finally block for session.close()' in diff_summary; metrics show db_connections growing linearly from 5 to 100.

red_herrings:
  1. Segment analytics failures — external service issue, completely unrelated to connection pool
  2. Certificate expiry warning — routine 45-day advance warning, has nothing to do with connections

correct_fix: fix_restart_app (risk_level 1) — restarts clear leaked connections immediately, hotfix adds the missing finally block
alternative: fix_connection_recycler (risk_level 0) — mitigates symptoms but does not fix the root cause
""")

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3: memory_leak
# ══════════════════════════════════════════════════════════════════════════════
S3 = DATA / "scenarios" / "memory_leak"

logs_s3 = []
routine_s3 = [
    ("INFO",  "GET /api/feed 200 88ms"),
    ("DEBUG", "Rendering template: dashboard.html"),
    ("INFO",  "POST /api/events 201 44ms"),
    ("INFO",  "Worker processed 12 tasks in queue"),
    ("DEBUG", "Cache eviction: 42 items removed (LRU)"),
    ("INFO",  "GET /api/metrics/summary 200 65ms"),
    ("DEBUG", "Scheduled cleanup task ran — 0 stale records"),
    ("INFO",  "PUT /api/users/settings 200 38ms"),
]
for i, (level, msg) in enumerate(routine_s3 * 10):
    logs_s3.append({"timestamp": ts(90 - i * 0.55), "level": level, "message": msg})

# Red herring 1: GC pause (normal for this workload size, not cause)
# Red herring 2: webhook delivery failure (unrelated customer event)
red_herrings_s3 = [
    ("WARNING", "GC pause time 250ms — within normal range for heap size (not an error)"),
    ("WARNING", "GC pause time 310ms — elevated but heap size is 1.8GB"),
    ("ERROR",   "Webhook delivery failed for customer 7291: HTTP 408 timeout — will retry"),
    ("WARNING", "Webhook retry queue depth: 8 pending for customer 7291"),
    ("INFO",    "GC completed in 180ms, freed 42MB"),
    ("WARNING", "Webhook delivery failed for customer 7291 after 3 retries — giving up"),
]
for i, (level, msg) in enumerate(red_herrings_s3 * 3):
    logs_s3.append({"timestamp": ts(85 - i * 3.5), "level": level, "message": msg})

signals_s3 = [
    ("WARNING", "Memory usage 68% (1740MB/2560MB) — above normal baseline of 512MB"),
    ("WARNING", "Memory usage 78% (1997MB/2560MB) — request logging middleware accumulating objects"),
    ("ERROR",   "Memory usage 89% (2278MB/2560MB) — heap growing, possible leak in request_logger module"),
    ("ERROR",   "Memory usage 92% (2355MB/2560MB) — request_body_log list has 48000 entries"),
    ("CRITICAL","Memory usage 97% (2483MB/2560MB) — OOMKiller likely imminent"),
    ("CRITICAL","OOMKiller activated: process 1234 (gunicorn worker) killed — restarting"),
    ("ERROR",   "Service restarted after OOM kill — memory back to baseline 512MB"),
    ("WARNING", "Memory climbing again: 720MB — leak is still present, restart only temporary fix"),
    ("ERROR",   "Module-level list 'request_body_log' in logging_middleware.py has 12000 entries after restart"),
    ("CRITICAL","Memory usage 85% (2176MB/2560MB) — same leak pattern repeating post-restart"),
]
for i, (level, msg) in enumerate(signals_s3):
    logs_s3.append({"timestamp": ts(55 - i * 3.5), "level": level, "message": msg})

logs_s3.sort(key=lambda r: r["timestamp"])
logs_s3 = logs_s3[:150]
write_csv(S3 / "logs.csv", logs_s3, ["timestamp", "level", "message"])

metrics_s3 = []
for i in range(60):
    t = ts(60 - i)
    if i < 10:
        mem = 512 + i * 15
    elif i == 42:  # OOM kill + restart
        mem = 520
    elif i > 42:
        mem = 520 + (i - 42) * 45
    else:
        mem = 512 + i * 55
    metrics_s3.append({
        "timestamp": t,
        "p95_latency_ms": 88 + max(0, (mem - 2000) // 20),
        "error_rate_pct": round(max(0, (mem - 2200) / 100), 2),
        "memory_mb": round(min(mem, 2560)),
        "db_connections": 10 + (i % 4),
    })
write_csv(S3 / "metrics.csv", metrics_s3,
          ["timestamp", "p95_latency_ms", "error_rate_pct", "memory_mb", "db_connections"])

deploys_s3 = [
    {"time": ts(400), "author": "iris",  "commit_message": "feat: implement GraphQL API layer", "files_changed": "api/graphql.py, schema/types.py", "diff_summary": "Added GraphQL endpoint with schema introspection"},
    {"time": ts(300), "author": "jake",  "commit_message": "fix: handle edge case in date parsing", "files_changed": "utils/dates.py", "diff_summary": "Fixed UTC offset parsing for ISO 8601 strings"},
    {"time": ts(200), "author": "karen", "commit_message": "chore: add prometheus metrics endpoint", "files_changed": "metrics/exporter.py", "diff_summary": "Added /metrics endpoint for Prometheus scraping"},
    {"time": ts(90),  "author": "iris",  "commit_message": "feat: add comprehensive request/response logging middleware for debugging", "files_changed": "middleware/logging_middleware.py, app.py, config.py", "diff_summary": "New middleware logs full request and response bodies for debugging. Stores entries in module-level list 'request_body_log = []' for later analysis. No max size limit or TTL implemented. Runs on every request."},
    {"time": ts(5),   "author": "jake",  "commit_message": "docs: update deployment runbook", "files_changed": "docs/runbook.md", "diff_summary": "Added rollback steps and health check commands"},
]
write_csv(S3 / "deploys.csv", deploys_s3,
          ["time", "author", "commit_message", "files_changed", "diff_summary"])

sandbox_s3 = {
    "fix_restart_service": {
        "description": "Emergency restart of all workers to clear accumulated memory (temporary — leak will recur)",
        "risk_level": 0,
        "blast_radius": "~20 seconds of downtime during rolling restart; memory returns to baseline but leak recurs without code fix",
        "after_metrics": {"p95_latency_ms": 90, "error_rate_pct": 0.05, "memory_mb": 525, "db_connections": 11},
    },
    "fix_patch_middleware": {
        "description": "Deploy hotfix: remove module-level 'request_body_log' accumulation from logging_middleware.py, replace with bounded deque(maxlen=1000) or remove entirely",
        "risk_level": 1,
        "blast_radius": "Rolling deploy ~15s elevated latency; request body logging disabled until fix reviewed; accumulated log data lost (was not persisted anyway)",
        "after_metrics": {"p95_latency_ms": 88, "error_rate_pct": 0.04, "memory_mb": 518, "db_connections": 10},
    },
    "fix_increase_memory": {
        "description": "Scale instance memory from 2.5GB to 8GB to delay OOM kills (does NOT fix leak)",
        "risk_level": 2,
        "blast_radius": "Full instance replacement required; costs 3x more; leak will fill 8GB in ~3 hours without code fix; misleading false stability",
        "after_metrics": {"p95_latency_ms": 88, "error_rate_pct": 0.04, "memory_mb": 2355, "db_connections": 10},
    },
}
write_json(S3 / "sandbox_effects.json", sandbox_s3)

write_text(S3 / "answer_key.txt", """root_cause: The deploy 90 minutes ago (iris, 'feat: add comprehensive request/response logging middleware') introduced a module-level list 'request_body_log = []' in logging_middleware.py that stores full request bodies for every incoming request with no size limit or TTL. The list grows unbounded, consuming all available memory (~2.5GB) in ~45-50 minutes, triggering the OOMKiller. Restarting clears memory temporarily but the leak immediately resumes.

evidence: logs show 'request_body_log list has 48000 entries after restart' and 'Module-level list request_body_log in logging_middleware.py'; deploy diff_summary says 'Stores entries in module-level list ... No max size limit or TTL implemented. Runs on every request.'; metrics show memory climbing from 512MB to 2560MB over 42 minutes in a straight line.

red_herrings:
  1. GC pause 250-310ms — this is caused BY the growing heap, not causing the leak; GC is trying (and failing) to keep up
  2. Webhook delivery failures for customer 7291 — completely unrelated, external webhook endpoint timeout

correct_fix: fix_patch_middleware (risk_level 1) — removes the unbounded accumulation
temporary_mitigation: fix_restart_service (risk_level 0) — clears memory but leak recurs in ~45min
wrong_fix: fix_increase_memory (risk_level 2) — does not fix leak, just delays OOM by a few hours
""")

print("Sample data generated successfully!")
print(f"  Scenarios: bad_deploy_slow_queries, connection_pool_leak, memory_leak")
print(f"  Past incidents: 20 entries")
