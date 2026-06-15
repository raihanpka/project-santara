"""A2A Protocol helpers: AgentCard, JSON-RPC client, JSON-RPC server base.

The A2A Protocol (Linux Foundation) is the contract between Python
services in the Santara platform. Agents publish a static AgentCard
at `/.well-known/agent-card.json` and answer questions over JSON-RPC
over HTTP. This module keeps the surface small: it does not define
the protocol, it lets services declare their card and answer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

import httpx

CARD_PATH = "/.well-known/agent-card.json"
JSONRPC_PATH = "/a2a"


@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass
class AgentCard:
    id: str
    name: str
    description: str
    url: str
    version: str = "0.1.0"
    skills: list[AgentSkill] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def make_agent_card(
    *,
    agent_id: str,
    name: str,
    description: str,
    url: str,
    skills: list[AgentSkill],
) -> AgentCard:
    return AgentCard(
        id=agent_id, name=name, description=description, url=url, skills=skills
    )


Handler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class A2AClient:
    """Minimal JSON-RPC over HTTP client."""

    def __init__(self, base_url: str, *, timeout_s: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def ask(self, question: str, *, context: dict[str, Any] | None = None) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "ask",
            "params": {"question": question, "context": context or {}},
        }
        r = await self._client.post(f"{self._base}{JSONRPC_PATH}", json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"A2A error: {data['error']}")
        return data["result"]["answer"]

    async def aclose(self) -> None:
        await self._client.aclose()
