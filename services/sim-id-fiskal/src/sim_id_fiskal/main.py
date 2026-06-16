"""FastAPI app exposing the fiscal stress test as a single endpoint.

The service is intentionally small. It does one thing: it answers
fiscal questions grounded in real data. For richer analysis, call
the Go sim-engine over gRPC and chain the result.

Error code scheme (harmonized across sim-id services):
  - 200 success
  - 400 business logic error (unknown fuel, unknown scenario)
  - 422 Pydantic schema validation error (out-of-range, missing field)
  - 500 unexpected server error

ponytail: request/response models live locally for now. A future
refactor will lift the scenario-specific Pydantic models into
sim-kernel/sim_id/schemas.py so gateway, sim-id-fiskal, and the
Go gRPC contracts share one source of truth.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sim_id_fiskal import FiscalStressTest
from sim_id_fiskal.dataset import latest_fuel_price

app = FastAPI(
    title="Santara sim-id-fiskal",
    description="Indonesian fiscal stress test. First anchor service in Project Santara.",
    version="0.1.0",
)

VALID_FUELS: frozenset[str] = frozenset({"pertamax", "pertalite", "solar"})

# Path to the bundled dataset Parquet. The container image ships
# the curated Parquet at this path. For local dev, the path can
# be overridden with the SIM_ID_FISKAL_DATASET env var.
DATASET_PATH = Path(
    os.environ.get(
        "SIM_ID_FISKAL_DATASET",
        "/app/data/id_fiscal_pressure/dist/train-00000-of-00001.parquet",
    )
)


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
    # ponytail: if the caller did not supply a latest price, look it
    # up from the curated dataset. If the dataset is missing, fall
    # back to a numeric-only shock report (no IDR/liter).
    latest_kwarg_name = f"latest_{req.fuel.lower()}_idr_per_liter"
    if req.latest_fuel_idr_per_liter is None:
        try:
            latest = latest_fuel_price(req.fuel, dataset_path=DATASET_PATH)
            latest_kwarg = {latest_kwarg_name: latest.price_idr_per_liter}
        except FileNotFoundError:
            latest_kwarg = {}
    else:
        latest_kwarg = {latest_kwarg_name: req.latest_fuel_idr_per_liter}
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
