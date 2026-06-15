"""Pydantic domain models for Project Santara.

Pure data containers. No I/O. No business logic. Services layer in
logic on top of these.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentKind(StrEnum):
    HOUSEHOLD = "household"
    FIRM = "firm"
    GOVERNMENT = "government"
    BANK = "bank"
    TRADER = "trader"
    FARMER = "farmer"


class ShockKind(StrEnum):
    FISCAL = "fiscal"
    POLITICAL = "political"
    CLIMATE = "climate"
    AGRARIAN = "agrarian"


class SimulationStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    DESTROYED = "destroyed"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=False)


class Agent(_Strict):
    id: str
    kind: AgentKind
    locale: str = "id"
    state: dict[str, float] = Field(default_factory=dict)

    @field_validator("state")
    @classmethod
    def _finite_numbers(cls, v: dict[str, Any]) -> dict[str, float]:
        return {k: float(val) for k, val in v.items()}


class Region(_Strict):
    id: str
    name: str
    country: str = "IDN"


class Market(_Strict):
    id: str
    name: str
    unit: str


class Shock(_Strict):
    id: str
    kind: ShockKind
    parameters: dict[str, float] = Field(default_factory=dict)
    tick_applied: int | None = None


class Simulation(_Strict):
    id: str
    scenario_id: str
    locale: str
    seed: int
    status: SimulationStatus = SimulationStatus.CREATED
    created_at_tick: int = 0
    agents: dict[str, Agent] = Field(default_factory=dict)
    shocks: list[Shock] = Field(default_factory=list)
    macro_indicators: dict[str, float] = Field(default_factory=dict)

    def is_alive(self) -> bool:
        return self.status != SimulationStatus.DESTROYED
