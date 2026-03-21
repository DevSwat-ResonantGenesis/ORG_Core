"""
Integration test for tool observability across all 3 systems.
Run: python3 -m pytest shared/tools/test_observability_integration.py -v
"""
import asyncio
import json
import sys
import os
import time

# Add project root to path so shared.tools resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from shared.tools.observability import ToolObserver, get_observer, ToolCallRecord


# ── Test: Agentic Chat pattern (manual __aenter__/__aexit__) ──

@pytest.mark.asyncio
async def test_agentic_chat_pattern():
    """Simulates the exact pattern used in routers_agentic_chat.py."""
    obs = ToolObserver(system="agentic_chat_test", log_every_call=False)
    user_id = "user-abc"
    conv_id = "conv-123"
    provider = "groq"

    # Simulate 3 tool calls in a loop
    for loop_count in range(1, 4):
        tool_name = ["web_search", "weather", "web_search"][loop_count - 1]
        tool_args = {"query": f"test {loop_count}"}

        _obs_ctx = obs.observe(
            tool_name, user_id=user_id, session_id=conv_id,
            loop_number=loop_count, provider=provider, args=tool_args,
        )
        _obs_handle = await _obs_ctx.__aenter__()

        # Simulate tool execution
        if loop_count == 2:
            tool_result = {"error": "Weather API timeout"}
        else:
            tool_result = {"results": [f"result_{loop_count}"]}

        result_str = json.dumps(tool_result, default=str)
        _truncated = len(result_str) > 8000
        if _truncated:
            result_str = result_str[:8000] + "...(truncated)"

        if isinstance(tool_result, dict) and tool_result.get("error"):
            _obs_handle.set_error(tool_result["error"])
        else:
            _obs_handle.set_result(result_str)
        _obs_handle.set_truncated(_truncated)
        await _obs_ctx.__aexit__(None, None, None)

    # Verify stats
    summary = obs.get_summary()
    assert summary["system"] == "agentic_chat_test"
    assert summary["total_calls"] == 3
    assert summary["total_failures"] == 1
    assert summary["unique_tools_used"] == 2

    ws_stats = obs.get_tool_stats("web_search")
    assert ws_stats["total_calls"] == 2
    assert ws_stats["success_count"] == 2

    w_stats = obs.get_tool_stats("weather")
    assert w_stats["total_calls"] == 1
    assert w_stats["failure_count"] == 1

    # Session records
    session_records = obs.get_records_for_session("conv-123")
    assert len(session_records) == 3

    # User records
    user_records = obs.get_records_for_user("user-abc")
    assert len(user_records) == 3


# ── Test: Public Chat pattern (async with) ──

@pytest.mark.asyncio
async def test_public_chat_pattern():
    """Simulates the exact pattern used in routers_public_chat.py."""
    obs = ToolObserver(system="public_chat_test", log_every_call=False)
    client_ip = "192.168.1.1"

    # Simulate guest tool call
    tool_name = "web_search"
    tool_args = {"query": "python tutorials"}

    async with obs.observe(
        tool_name, user_id=client_ip, session_id="",
        loop_number=1, provider="groq", args=tool_args,
    ) as _obs:
        # Simulate handler execution
        tool_result = {"results": [{"title": "Python Tutorial", "url": "https://python.org"}]}
        _obs.set_result(tool_result)

    stats = obs.get_tool_stats("web_search")
    assert stats["total_calls"] == 1
    assert stats["success_count"] == 1
    assert stats["avg_latency_ms"] >= 0

    # Simulate error
    async with obs.observe("fetch_url", user_id=client_ip, provider="groq") as _obs:
        tool_result = {"error": "Connection refused"}
        _obs.set_error(tool_result["error"])

    fetch_stats = obs.get_tool_stats("fetch_url")
    assert fetch_stats["failure_count"] == 1
    assert "Connection refused" in list(fetch_stats["top_errors"].keys())[0]


# ── Test: Executor pattern (async with, agent_id) ──

@pytest.mark.asyncio
async def test_executor_pattern():
    """Simulates the exact pattern used in executor.py."""
    obs = ToolObserver(system="executor_test", log_every_call=False)

    agent_id = "agent-xyz-789"
    user_id = "user-456"
    loop_num = 3

    async with obs.observe(
        "web_search", user_id=user_id, agent_id=agent_id,
        loop_number=loop_num, args={"query": "test"},
    ) as _obs:
        result = {"results": [{"title": "Test", "url": "https://test.com"}]}
        _obs.set_result(result)

    async with obs.observe(
        "execute_code", user_id=user_id, agent_id=agent_id,
        loop_number=loop_num + 1, args={"code": "print(1+1)", "language": "python"},
    ) as _obs:
        result = {"output": "2", "exit_code": 0}
        _obs.set_result(result)

    summary = obs.get_summary()
    assert summary["total_calls"] == 2
    assert summary["unique_tools_used"] == 2

    records = obs.get_recent_records(10)
    assert len(records) == 2
    assert all(r["system"] == "executor_test" for r in records)


# ── Test: Global observer singletons ──

@pytest.mark.asyncio
async def test_global_observer_singletons():
    """Verify get_observer returns the same instance for same system name."""
    obs1 = get_observer("agentic_chat")
    obs2 = get_observer("agentic_chat")
    obs3 = get_observer("public_chat")
    obs4 = get_observer("executor")

    assert obs1 is obs2
    assert obs1 is not obs3
    assert obs3 is not obs4

    # All have correct system names
    assert obs1.system == "agentic_chat"
    assert obs3.system == "public_chat"
    assert obs4.system == "executor"


# ── Test: Cross-system summary (what the API endpoint does) ──

@pytest.mark.asyncio
async def test_cross_system_summary():
    """Simulates what /observability/summary endpoint does."""
    # Create isolated observers for this test
    observers = {
        "sys_a": ToolObserver(system="sys_a", log_every_call=False),
        "sys_b": ToolObserver(system="sys_b", log_every_call=False),
    }

    # Add some calls
    async with observers["sys_a"].observe("web_search", user_id="u1") as ctx:
        ctx.set_result("ok")
    async with observers["sys_a"].observe("weather", user_id="u2") as ctx:
        ctx.set_error("timeout")
    async with observers["sys_b"].observe("execute_code", user_id="u1") as ctx:
        ctx.set_result("ok")

    # Aggregate like the API endpoint does
    result = {}
    for sys_name, obs in observers.items():
        result[sys_name] = obs.get_summary()

    assert result["sys_a"]["total_calls"] == 2
    assert result["sys_a"]["total_failures"] == 1
    assert result["sys_b"]["total_calls"] == 1
    assert result["sys_b"]["total_failures"] == 0


# ── Test: Tool log line format ──

def test_log_line_format():
    """Verify structured log line format for ELK/Loki ingestion."""
    rec = ToolCallRecord(
        tool_name="web_search",
        system="agentic_chat",
        user_id="user-123",
        session_id="conv-456",
        success=True,
        latency_ms=230.5,
        result_chars=2500,
        total_tokens=700,
        loop_number=2,
        provider="groq",
    )
    line = rec.to_log_line()
    assert "[TOOL]" in line
    assert "agentic_chat" in line
    assert "web_search" in line
    assert "OK" in line
    assert "230ms" in line
    assert "user=user-123" in line
    assert "session=conv-456" in line
    assert "provider=groq" in line


# ── Test: High-volume stress test ──

@pytest.mark.asyncio
async def test_high_volume():
    """Verify observer handles many calls without issues."""
    obs = ToolObserver(system="stress_test", log_every_call=False, max_records=500)

    for i in range(200):
        async with obs.observe(f"tool_{i % 10}", user_id=f"u{i % 5}") as ctx:
            if i % 7 == 0:
                ctx.set_error("random error")
            else:
                ctx.set_result(f"result_{i}")

    summary = obs.get_summary()
    assert summary["total_calls"] == 200
    assert summary["unique_tools_used"] == 10
    assert len(obs.get_recent_records(1000)) <= 500  # max_records cap


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
