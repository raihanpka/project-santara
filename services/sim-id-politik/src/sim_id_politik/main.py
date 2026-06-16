"""FastAPI app for sim-id-politik."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sim_id_politik.anchor import PoliticalDynamics

app = FastAPI(
    title="Santara sim-id-politik",
    description="Indonesia political dynamics. Second anchor service in Project Santara.",
    version="0.2.0",
)

VALID_SCENARIOS: frozenset[str] = frozenset({"mbg_swing_voter_2029"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    scenario: str = Field("mbg_swing_voter_2029")
    mbg_coverage_pct: float = Field(..., ge=0, le=100)
    satisfaction_score: float = Field(..., ge=0, le=100)
    base_swing_rate_pct: float = Field(..., gt=0, le=30)


class AskResponse(BaseModel):
    question: str
    result: dict[str, Any]


engine = PoliticalDynamics()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    if req.scenario not in VALID_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {req.scenario!r}. Use one of: {sorted(VALID_SCENARIOS)}.",
        )
    try:
        result = engine.apply(
            mbg_coverage_pct=req.mbg_coverage_pct,
            satisfaction_score=req.satisfaction_score,
            base_swing_rate_pct=req.base_swing_rate_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AskResponse(question=req.question, result=result.to_dict())
