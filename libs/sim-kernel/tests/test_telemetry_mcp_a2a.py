"""Tests for sim-kernel telemetry and a2a/mcp helpers."""

from __future__ import annotations

import asyncio

import pytest

from sim_kernel.a2a import (
    JSONRPC_PATH,
    AgentSkill,
    make_agent_card,
)
from sim_kernel.mcp import MCPServerBase
from sim_kernel.telemetry import get_meter, get_tracer


def test_tracer_no_op_when_disabled() -> None:
    tracer = get_tracer()
    with tracer.start_as_current_span("x"):
        pass  # must not raise


def test_meter_no_op_when_disabled() -> None:
    meter = get_meter()
    counter = meter.create_counter("x")
    counter.add(1)


def test_agent_card_to_dict() -> None:
    card = make_agent_card(
        agent_id="fiskal",
        name="Santara Fiscal",
        description="Indonesian fiscal stress test",
        url="https://example.test",
        skills=[AgentSkill(id="ask", name="Ask", description="Answer a question")],
    )
    d = card.to_dict()
    assert d["id"] == "fiskal"
    assert d["skills"][0]["id"] == "ask"
    assert JSONRPC_PATH.startswith("/")


def test_mcp_register_and_call() -> None:
    server = MCPServerBase("test")

    @server.tool(name="add", description="Add two numbers")
    async def add(a: int, b: int) -> int:
        return a + b

    tools = server.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "add"
    assert tools[0].input_schema["required"] == ["a", "b"]

    result = asyncio.run(server.call_tool("add", {"a": 2, "b": 3}))
    assert result == 5


def test_mcp_unknown_tool_raises() -> None:
    server = MCPServerBase("test")

    async def run() -> None:
        await server.call_tool("nope", {})

    with pytest.raises(KeyError):
        asyncio.run(run())


def test_mcp_optional_args_not_required() -> None:
    server = MCPServerBase("test")

    @server.tool(name="greet", description="Greet")
    async def greet(name: str = "world") -> str:
        return f"hello {name}"

    tool = server.list_tools()[0]
    assert "required" not in tool.input_schema or tool.input_schema.get("required") is None
