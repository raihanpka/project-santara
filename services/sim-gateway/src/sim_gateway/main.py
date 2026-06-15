"""FastAPI app for sim-gateway.

Endpoints:
  GET  /healthz                        liveness
  GET  /.well-known/agent-card.json    A2A AgentCard
  POST /a2a                            A2A JSON-RPC entry

For v0.1.0 the gateway only forwards "ask" calls to sim-id-fiskal
via HTTP. gRPC to sim-engine, MCP server hub, and full JWT are
later phases.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sim_kernel.a2a import (
    AgentSkill,
    CARD_PATH,
    make_agent_card,
)

FISKAL_URL = os.environ.get("SIM_ID_FISKAL_URL", "http://sim-id-fiskal:8001")
GATEWAY_JWT_SECRET = os.environ.get("GATEWAY_JWT_SECRET", "ponytail: dev only, replace in prod")  # ponytail:

app = FastAPI(
    title="Santara sim-gateway",
    description="A2A router, MCP server hub (planned), JWT auth.",
    version="0.1.0",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get(CARD_PATH)
def agent_card() -> dict[str, Any]:
    card = make_agent_card(
        agent_id="santara-gateway",
        name="Santara Gateway",
        description="Routes A2A requests to Indonesian anchor services.",
        url=os.environ.get("GATEWAY_PUBLIC_URL", "https://santara.id"),
        skills=[
            AgentSkill(
                id="ask_fiskal",
                name="Ask a fiscal question",
                description=(
                    "Route a Bahasa Indonesia or English question about Indonesian "
                    "fiscal stress to the sim-id-fiskal service."
                ),
                examples=[
                    "Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?",
                    "What happens to inflation if Pertamax rises 30 percent?",
                ],
            ),
        ],
    )
    return card.to_dict()


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcError(BaseModel):
    code: int
    message: str


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    result: dict[str, Any] | None = None
    error: JsonRpcError | None = None


def _check_bearer(request: Request) -> None:
    """Verify the bearer token. Raises 401 on failure."""
    import jwt  # ponytail: import only when needed to keep cold start light

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth[len("Bearer ") :]
    try:
        jwt.decode(token, GATEWAY_JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


@app.post("/a2a", response_model=JsonRpcResponse)
async def a2a(req: JsonRpcRequest, request: Request) -> JSONResponse:
    if req.method != "ask":
        return JSONResponse(
            status_code=200,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(code=-32601, message=f"Method not found: {req.method}").model_dump(),
            ).model_dump(),
        )

    _check_bearer(request)
    question = req.params.get("question", "")
    fuel = req.params.get("fuel", "pertamax")
    shock_pct = req.params.get("shock_pct", 30.0)
    if not question:
        return JSONResponse(
            status_code=200,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(code=-32602, message="Missing 'question' in params").model_dump(),
            ).model_dump(),
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{FISKAL_URL}/ask",
            json={
                "question": question,
                "fuel": fuel,
                "shock_pct": shock_pct,
            },
        )
        r.raise_for_status()
        fiskal_result = r.json()["result"]

    return JSONResponse(
        content=JsonRpcResponse(
            id=req.id,
            result={"answer": fiskal_result["notes"], "details": fiskal_result},
        ).model_dump(),
    )
