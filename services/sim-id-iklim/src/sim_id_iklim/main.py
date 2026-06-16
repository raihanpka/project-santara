"""FastAPI app for sim-id-iklim."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sim_id_iklim.anchor import ClimateEmergency

app = FastAPI(
    title="Santara sim-id-iklim",
    description="Indonesia climate emergency. Third anchor service in Project Santara.",
    version="0.2.0",
)

VALID_SCENARIOS: frozenset[str] = frozenset({"karhutla_riau_haze"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    scenario: str = Field("karhutla_riau_haze")
    hotspots: int = Field(..., ge=0)
    wind_speed_kmh: float = Field(..., gt=0)
    dry_days: int = Field(..., ge=0)


class AskResponse(BaseModel):
    question: str
    result: dict[str, Any]


engine = ClimateEmergency()


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
            hotspots=req.hotspots,
            wind_speed_kmh=req.wind_speed_kmh,
            dry_days=req.dry_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AskResponse(question=req.question, result=result.to_dict())
