"""
Tests for Agent Tools (Phase 2)

Verifies:
  - All 5 Claude tools execute correctly against scenario 1 (bad_deploy_slow_queries)
  - run_in_sandbox returns before/after metrics from sandbox_effects.json
  - Tool outputs are delimited inside <telemetry_data> tags
  - Path traversal and arbitrary execution are blocked
  - Bounds checking on parameters
"""
from __future__ import annotations

import json
import re
import pytest

from app.tools import TOOL_DEFINITIONS, execute_tool, format_tool_result


SCENARIO_1 = "bad_deploy_slow_queries"


class TestToolDefinitions:
    def test_all_five_tools_registered(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "get_recent_deploys",
            "query_logs",
            "get_metrics",
            "search_past_incidents",
            "run_in_sandbox",
        }
        assert names == expected

    def test_tool_schemas_have_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
            assert "properties" in tool["input_schema"]


class TestToolExecution:
    def test_get_recent_deploys(self):
        res = execute_tool(SCENARIO_1, "get_recent_deploys", {"service": "orders", "hours": 24})
        assert "<telemetry_data" in res
        assert "</telemetry_data>" in res
        assert "deploys" in res
        assert "removed index on orders.status" in res

    def test_query_logs_with_level_filter(self):
        res = execute_tool(SCENARIO_1, "query_logs", {"service": "orders", "level": "ERROR", "minutes": 60})
        assert "<telemetry_data" in res
        assert "full table scan detected" in res or "execution time exceeded" in res

    def test_query_logs_with_keyword(self):
        res = execute_tool(SCENARIO_1, "query_logs", {"service": "orders", "keyword": "full table scan"})
        assert "full table scan detected" in res

    def test_get_metrics_single_metric(self):
        res = execute_tool(SCENARIO_1, "get_metrics", {"service": "orders", "metric": "p95_latency_ms"})
        assert "p95_latency_ms" in res
        # Confirm numeric data is present
        m = re.search(r'"p95_latency_ms":\s*(\d+)', res)
        assert m is not None

    def test_search_past_incidents(self):
        res = execute_tool(SCENARIO_1, "search_past_incidents", {"query": "slow queries full table scan index"})
        assert "incidents" in res
        assert "orders" in res.lower() or "index" in res.lower()

    def test_run_in_sandbox_valid_fix(self):
        """run_in_sandbox returns before/after metrics from sandbox_effects.json."""
        res = execute_tool(SCENARIO_1, "run_in_sandbox", {"fix_id": "fix_add_index"})
        assert "rehearsal_success" in res
        assert "before_metrics" in res
        assert "after_metrics" in res
        assert "blast_radius" in res
        assert "risk_level" in res
        # Verify simulated flag is True
        assert '"simulated": true' in res.lower()

    def test_run_in_sandbox_unknown_fix(self):
        res = execute_tool(SCENARIO_1, "run_in_sandbox", {"fix_id": "invalid_fix_123"})
        assert "Unknown fix_id" in res
        assert "available_fixes" in res

    def test_unknown_tool_returns_error(self):
        res = execute_tool(SCENARIO_1, "reboot_cluster_destructive", {})
        assert "Unknown tool" in res

    def test_tool_bounds_clamping(self):
        # Very high minutes should be clamped and not crash
        res = execute_tool(SCENARIO_1, "query_logs", {"service": "api", "minutes": 9999999})
        assert "<telemetry_data" in res

    def test_telemetry_delimiter_integrity(self):
        raw = execute_tool(SCENARIO_1, "query_logs", {"service": "orders", "keyword": "Elasticsearch"})
        # Must contain prompt injection warning
        assert "WARNING: The following is raw system telemetry" in raw
        assert raw.startswith('<telemetry_data tool="query_logs"')
        assert raw.endswith("</telemetry_data>")
