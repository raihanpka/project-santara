"""FastAPI app exposing the fiscal stress test as a single endpoint.

The service is intentionally small. It does one thing: it answers
fiscal questions grounded in real data. For richer analysis, call
the Go sim-engine over gRPC and chain the result.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sim_id_fiskal import FiscalStressTest

app = FastAPI(
    title="Santara sim-id-fiskal",
    description="Indonesian fiscal stress test. First anchor service in Project Santara.",
    version="0.1.0",
)

VALID_FUELS: frozenset[str] = frozenset({"pertamax", "pertalite", "solar"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    fuel: str = Field("pertamax")
    shock_pct: float = Field(..., gt=-100, lt=200)
    as_of: date | None = None
    latest_fuel_idr_per_liter: float | None = None


class AskResponse(BaseModel):
    question: str
    result: dict[str, Any]


engine = FiscalStressTest()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    if req.fuel.lower() not in VALID_FUELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown fuel: {req.fuel!r}. Use one of: {sorted(VALID_FUELS)}.",
        )
    latest_kwarg = {f"latest_{req.fuel.lower()}_idr_per_liter": req.latest_fuel_idr_per_liter}
    try:
        result = engine.apply(
            fuel=req.fuel,
            shock_pct=req.shock_pct,
            as_of=req.as_of or date.today(),
            **latest_kwarg,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AskResponse(question=req.question, result=result.to_dict())
