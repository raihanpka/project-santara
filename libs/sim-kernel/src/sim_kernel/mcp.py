"""MCP server base and tool decorator.

The Model Context Protocol (Linux Foundation) lets Santara services
expose tools and data to agents. This module keeps the surface tiny:
one decorator, one base class, one method to list tools and call them.
We do not depend on the `mcp` package at import time; it is only
required when the service actually serves MCP.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ToolFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPServerBase:
    """Register tools with a decorator; serve them via `call_tool`."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, tuple[ToolSpec, ToolFn]] = {}

    def tool(self, *, name: str, description: str) -> Callable[[ToolFn], ToolFn]:
        def deco(fn: ToolFn) -> ToolFn:
            sig = inspect.signature(fn)
            properties: dict[str, Any] = {}
            required: list[str] = []
            for pname, param in sig.parameters.items():
                ptype = "string"
                if param.annotation is int:
                    ptype = "integer"
                elif param.annotation is float:
                    ptype = "number"
                elif param.annotation is bool:
                    ptype = "boolean"
                properties[pname] = {"type": ptype}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
            schema: dict[str, Any] = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            spec = ToolSpec(name=name, description=description, input_schema=schema)
            self._tools[name] = (spec, fn)
            return fn

        return deco

    def list_tools(self) -> list[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name!r}")
        _, fn = self._tools[name]
        return await fn(**arguments)
