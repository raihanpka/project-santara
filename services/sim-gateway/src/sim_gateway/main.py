"""FastAPI app for sim-gateway.

Endpoints:
  GET  /healthz                        liveness
  GET  /.well-known/agent-card.json    A2A AgentCard
  POST /a2a                            A2A JSON-RPC entry

For v0.2.0 the gateway routes by scenario to the matching sim-id
service. JWT is HS256 with aud and iss enforced. Structured logging
via structlog.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sim_kernel.a2a import (
    CARD_PATH,
    AgentSkill,
    make_agent_card,
)

FISKAL_URL = os.environ.get("SIM_ID_FISKAL_URL", "http://sim-id-fiskal:8001")
POLITIK_URL = os.environ.get("SIM_ID_POLITIK_URL", "http://sim-id-politik:8002")
IKLIM_URL = os.environ.get("SIM_ID_IKLIM_URL", "http://sim-id-iklim:8003")
GATEWAY_JWT_SECRET = os.environ.get(
    "GATEWAY_JWT_SECRET", "ponytail: dev only, replace in prod"
)
GATEWAY_JWT_AUDIENCE = os.environ.get("GATEWAY_JWT_AUDIENCE", "santara-gateway")
GATEWAY_JWT_ISSUER = os.environ.get("GATEWAY_JWT_ISSUER", "santara")

log = structlog.get_logger()


class Scenario(StrEnum):
    PERTAMAX_30PCT = "pertamax_30pct"
    MBG_SWING_VOTER_2029 = "mbg_swing_voter_2029"
    KARHUTLA_RIAU_HAZE = "karhutla_riau_haze"


SCENARIO_TO_URL: dict[Scenario, str] = {
    Scenario.PERTAMAX_30PCT: FISKAL_URL,
    Scenario.MBG_SWING_VOTER_2029: POLITIK_URL,
    Scenario.KARHUTLA_RIAU_HAZE: IKLIM_URL,
}


# ponytail: warn loudly when the dev default secret is in use.
if GATEWAY_JWT_SECRET.startswith("ponytail:"):
    log.warning("gateway.jwt.dev_secret_in_use", message="Replace GATEWAY_JWT_SECRET before production.")

app = FastAPI(
    title="Santara sim-gateway",
    description="A2A router, MCP server hub (planned), JWT auth (HS256 with aud and iss).",
    version="0.2.0",
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
            AgentSkill(
                id="ask_politik",
                name="Ask a political question",
                description=(
                    "Route a Bahasa Indonesia or English question about Indonesian "
                    "political dynamics to the sim-id-politik service."
                ),
                examples=[
                    "Apa dampak MBG terhadap swing voter di 2029?",
                ],
            ),
            AgentSkill(
                id="ask_iklim",
                name="Ask a climate question",
                description=(
                    "Route a Bahasa Indonesia or English question about Indonesian "
                    "climate emergency to the sim-id-iklim service."
                ),
                examples=[
                    "Kapan karhutla Riau menjadi krisis haze lintas batas?",
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
    """Verify the bearer token. Raises 401 on failure.

    HS256 with aud and iss enforced. exp is enforced by default by pyjwt.
    """
    import jwt  # ponytail: import only when needed to keep cold start light

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth[len("Bearer ") :]
    try:
        jwt.decode(
            token,
            GATEWAY_JWT_SECRET,
            algorithms=["HS256"],
            audience=GATEWAY_JWT_AUDIENCE,
            issuer=GATEWAY_JWT_ISSUER,
        )
    except jwt.PyJWTError as e:
        log.warning("gateway.jwt.invalid", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


@app.post("/a2a", response_model=JsonRpcResponse)
async def a2a(req: JsonRpcRequest, request: Request) -> JSONResponse:
    # JSON-RPC protocol errors return HTTP 200 with the error in
    # the body. HTTP 4xx is reserved for transport-level issues
    # (missing or invalid bearer is 401, downstream validation
    # surfaces as 502). This matches the JSON-RPC 2.0 spec.
    if req.method != "ask":
        return JSONResponse(
            status_code=200,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(
                    code=-32601, message=f"Method not found: {req.method}"
                ).model_dump(),
            ).model_dump(),
        )

    _check_bearer(request)
    question = req.params.get("question", "")
    scenario_str = req.params.get("scenario", Scenario.PERTAMAX_30PCT.value)

    try:
        scenario = Scenario(scenario_str)
    except ValueError:
        log.info("gateway.scenario.unknown", scenario=scenario_str)
        return JSONResponse(
            status_code=200,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(
                    code=-32602,
                    message=(
                        f"Unknown scenario: {scenario_str!r}. "
                        f"Use one of: {[s.value for s in Scenario]}"
                    ),
                ).model_dump(),
            ).model_dump(),
        )

    if not question:
        return JSONResponse(
            status_code=200,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(
                    code=-32602, message="Missing 'question' in params"
                ).model_dump(),
            ).model_dump(),
        )

    target_url = SCENARIO_TO_URL[scenario]
    service_body: dict[str, Any] = {"question": question, "scenario": scenario.value}
    for key, value in req.params.items():
        if key not in ("question", "scenario"):
            service_body[key] = value

    log.info("gateway.forward", scenario=scenario.value, target=target_url)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{target_url}/ask", json=service_body)
            r.raise_for_status()
            service_result = r.json()["result"]
    except httpx.HTTPStatusError as e:
        log.warning(
            "gateway.downstream.http_error",
            scenario=scenario.value,
            status=e.response.status_code,
        )
        return JSONResponse(
            status_code=502,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(
                    code=-32603,
                    message=f"Downstream service error: {e.response.status_code}",
                ).model_dump(),
            ).model_dump(),
        )
    except httpx.RequestError as e:
        log.warning("gateway.downstream.unavailable", scenario=scenario.value, error=str(e))
        return JSONResponse(
            status_code=502,
            content=JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(
                    code=-32603,
                    message=f"Downstream service unavailable: {e}",
                ).model_dump(),
            ).model_dump(),
        )

    return JSONResponse(
        content=JsonRpcResponse(
            id=req.id,
            result={"answer": service_result.get("notes", ""), "details": service_result},
        ).model_dump(),
    )
