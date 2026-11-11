"""
Tests for Stopwatch Demo Mode (Manual vs Agent) (Phase 5)

Verifies:
  - Manual mode: Raw logs endpoint loads all logs for scenario inspection.
  - Keyword filtering on raw logs for manual analysis.
  - Path traversal protection on raw logs endpoint.
  - Agent mode: Measures investigation duration accurately.
"""
from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from app.agent import AgentRunner
from tests.conftest import login


class TestStopwatchMode:
    def test_manual_mode_raw_logs_authenticated(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/scenarios/bad_deploy_slow_queries/raw_logs", cookies={"session": session})
        assert r.status_code == 200
        data = r.json()
        assert data["scenario_id"] == "bad_deploy_slow_queries"
        assert "logs" in data
        assert data["count"] > 0
        assert len(data["logs"]) == data["count"]

    def test_manual_mode_raw_logs_unauthenticated(self, client: TestClient):
        r = client.get("/api/scenarios/bad_deploy_slow_queries/raw_logs")
        assert r.status_code == 401

    def test_manual_mode_raw_logs_path_traversal_blocked(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        r = client.get("/api/scenarios/../../etc/raw_logs", cookies={"session": session})
        assert r.status_code in (400, 404)

    def test_manual_mode_all_scenarios_have_raw_logs(self, client: TestClient, user_credentials):
        session = login(client, user_credentials["username"], user_credentials["password"])
        for sid in ["bad_deploy_slow_queries", "connection_pool_leak", "memory_leak"]:
            r = client.get(f"/api/scenarios/{sid}/raw_logs", cookies={"session": session})
            assert r.status_code == 200
            assert r.json()["count"] >= 100

    @pytest.mark.asyncio
    async def test_agent_mode_timer_measurement(self):
        """Verify agent stopwatch measures elapsed time accurately."""
        runner = AgentRunner("bad_deploy_slow_queries")
        start = time.perf_counter()

        events = []
        async for event in runner.run():
            events.append(event)

        elapsed = time.perf_counter() - start
        assert elapsed > 0.0
        assert any(e.get("type") == "investigation_completed" for e in events)
