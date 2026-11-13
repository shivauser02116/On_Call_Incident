"""
Tests for Phase 9: Plan, Replan, and Agent Trace

Verifies:
  - Agent emits a short structured plan first (ordered checks and why)
  - Plan events conform strictly to PlanEvent schema
  - Replan event is emitted when findings change the plan (e.g., ambiguous_escalate and config_change_flag)
  - Replan events conform strictly to ReplanEvent schema with a clear reason
  - Tool call results include duration_ms, summary, and arguments
  - Completed event includes elapsed_ms and tokens_used
"""
import pytest
from app.agent import AgentRunner
from app.models import PlanEvent, ReplanEvent, PlanStep

@pytest.mark.asyncio
async def test_agent_emits_initial_plan():
    """Verify initial plan event is emitted on scenario 1."""
    runner = AgentRunner("bad_deploy_slow_queries")
    events = []
    async for event in runner.run():
        events.append(event)

    event_types = [e["type"] for e in events]
    assert "investigation_started" in event_types
    assert "plan" in event_types

    # Find plan event
    plan_idx = event_types.index("plan")
    start_idx = event_types.index("investigation_started")
    assert plan_idx > start_idx, "Plan must be emitted after investigation starts"

    plan_ev = events[plan_idx]
    validated = PlanEvent.model_validate(plan_ev)
    assert len(validated.steps) >= 4
    # Ordered step numbers
    step_nums = [s.step for s in validated.steps]
    assert step_nums == sorted(step_nums)
    # Check that tools and descriptions are present
    for step in validated.steps:
        assert step.tool in {"get_metrics", "query_logs", "get_recent_deploys", "search_past_incidents", "run_in_sandbox"}
        assert len(step.description) > 10

@pytest.mark.asyncio
async def test_agent_emits_replan_on_ambiguous_escalate():
    """Verify replan event is emitted when telemetry requires pivoting to escalation."""
    runner = AgentRunner("ambiguous_escalate")
    events = []
    async for event in runner.run():
        events.append(event)

    event_types = [e["type"] for e in events]
    assert "plan" in event_types
    assert "replan" in event_types

    replan_ev = next(e for e in events if e["type"] == "replan")
    validated = ReplanEvent.model_validate(replan_ev)
    assert len(validated.reason) > 15
    assert "conflicting" in validated.reason.lower() or "escalat" in validated.reason.lower()
    assert len(validated.steps) >= 4

@pytest.mark.asyncio
async def test_agent_emits_replan_on_config_change_flag():
    """Verify replan event is emitted when findings reveal dynamic config mutation instead of code deploy."""
    runner = AgentRunner("config_change_flag")
    events = []
    async for event in runner.run():
        events.append(event)

    event_types = [e["type"] for e in events]
    assert "plan" in event_types
    assert "replan" in event_types

    replan_ev = next(e for e in events if e["type"] == "replan")
    validated = ReplanEvent.model_validate(replan_ev)
    assert len(validated.reason) > 15
    assert "config" in validated.reason.lower()

@pytest.mark.asyncio
async def test_trace_duration_summary_and_totals():
    """Verify tool call results include duration_ms and summary, and completion has totals."""
    runner = AgentRunner("bad_deploy_slow_queries")
    events = []
    async for event in runner.run():
        events.append(event)

    tool_results = [e for e in events if e["type"] == "tool_call_result"]
    assert len(tool_results) >= 4

    for tr in tool_results:
        assert "duration_ms" in tr
        assert isinstance(tr["duration_ms"], int)
        assert tr["duration_ms"] > 0
        assert "summary" in tr
        assert len(tr["summary"]) > 5
        assert "arguments" in tr

    completed = next(e for e in events if e["type"] == "investigation_completed")
    assert "elapsed_ms" in completed
    assert isinstance(completed["elapsed_ms"], int)
    assert completed["elapsed_ms"] > 0
    assert "tokens_used" in completed
    assert isinstance(completed["tokens_used"], int)
    assert completed["tokens_used"] > 0

from app.tools import TOOL_DEFINITIONS, execute_tool
from app.agent import SYSTEM_PROMPT
import json

def test_plan_and_replan_tools_in_tool_definitions():
    """Verify formulate_plan and replan exist in TOOL_DEFINITIONS with valid schemas."""
    tools_by_name = {t["name"]: t for t in TOOL_DEFINITIONS}
    assert "formulate_plan" in tools_by_name
    assert "replan" in tools_by_name

    fp = tools_by_name["formulate_plan"]
    assert "steps" in fp["input_schema"]["properties"]
    assert fp["input_schema"]["required"] == ["steps"]

    rp = tools_by_name["replan"]
    assert "reason" in rp["input_schema"]["properties"]
    assert "steps" in rp["input_schema"]["properties"]
    assert set(rp["input_schema"]["required"]) == {"reason", "steps"}

    # Test execution
    res1 = execute_tool("bad_deploy_slow_queries", "formulate_plan", {"steps": [{"id": "s1", "label": "test", "reason": "why"}]})
    assert "plan_recorded" in res1

    res2 = execute_tool("bad_deploy_slow_queries", "replan", {"reason": "pivoting", "steps": []})
    assert "replan_recorded" in res2

def test_system_prompt_wording_rules():
    """Verify SYSTEM_PROMPT instructs 'the practice run showed' and never 'proved'."""
    assert "the practice run showed" in SYSTEM_PROMPT
    assert "never use the word \"proved\"" in SYSTEM_PROMPT.lower()
    assert "proving why they are less likely" not in SYSTEM_PROMPT

@pytest.mark.asyncio
async def test_simulated_events_have_is_mock_flag():
    """Verify mock mode sets is_mock=True on plan, replan, trace, and completion."""
    runner = AgentRunner("ambiguous_escalate")
    events = []
    async for event in runner.run():
        events.append(event)

    plan_ev = next(e for e in events if e["type"] == "plan")
    assert plan_ev.get("is_mock") is True
    assert plan_ev.get("source") == "model"

    replan_ev = next(e for e in events if e["type"] == "replan")
    assert replan_ev.get("is_mock") is True
    assert replan_ev.get("source") == "model"

    tool_results = [e for e in events if e["type"] == "tool_call_result"]
    for tr in tool_results:
        assert tr.get("is_mock") is True

    completed = next(e for e in events if e["type"] == "investigation_completed")
    assert completed.get("is_mock") is True

@pytest.mark.asyncio
async def test_simulated_rationale_wording_and_no_lock_contradiction():
    """Verify simulated results say 'the practice run showed' and do not claim orders table locked."""
    for scenario in ["bad_deploy_slow_queries", "memory_leak", "config_change_flag"]:
        runner = AgentRunner(scenario)
        result = runner._generate_simulated_result()
        assert "proved" not in result.proposed_fix.rationale.lower()
        assert "the practice run showed" in result.proposed_fix.rationale.lower()

    # Specifically check bad_deploy_slow_queries
    runner = AgentRunner("bad_deploy_slow_queries")
    result = runner._generate_simulated_result()
    assert "orders table locked" not in result.proposed_fix.blast_radius.lower()
    assert "create index concurrently" in result.proposed_fix.blast_radius.lower()
