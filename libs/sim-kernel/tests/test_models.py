"""Tests for sim-kernel models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sim_kernel.models import (
    Agent,
    AgentKind,
    Market,
    Region,
    Shock,
    ShockKind,
    Simulation,
    SimulationStatus,
)


def test_agent_basic() -> None:
    a = Agent(id="a1", kind=AgentKind.HOUSEHOLD, locale="id", state={"income": 1000.0})
    assert a.id == "a1"
    assert a.kind == AgentKind.HOUSEHOLD
    assert a.state["income"] == 1000.0


def test_agent_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        Agent(id="a1", kind="unicorn")  # type: ignore[arg-type]


def test_agent_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Agent(id="a1", kind=AgentKind.HOUSEHOLD, weird=True)  # type: ignore[call-arg]


def test_agent_state_coerces_to_float() -> None:
    a = Agent(id="a1", kind=AgentKind.FIRM, state={"x": "3.14", "y": 2})
    assert a.state == {"x": 3.14, "y": 2.0}


def test_simulation_starts_created() -> None:
    s = Simulation(id="s1", scenario_id="fiscal_001", locale="id", seed=42)
    assert s.status == SimulationStatus.CREATED
    assert s.is_alive()
    s.status = SimulationStatus.DESTROYED
    assert not s.is_alive()


def test_shock_kind() -> None:
    sh = Shock(id="sh1", kind=ShockKind.FISCAL, parameters={"pertamax_pct": 30.0})
    assert sh.parameters["pertamax_pct"] == 30.0


def test_region_and_market() -> None:
    r = Region(id="jkt", name="Jakarta", country="IDN")
    m = Market(id="brt", name="Beras", unit="IDR_per_kg")
    assert r.country == "IDN"
    assert m.unit == "IDR_per_kg"
