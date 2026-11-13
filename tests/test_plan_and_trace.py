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
