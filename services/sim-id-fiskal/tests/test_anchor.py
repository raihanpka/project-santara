"""Tests for the fiscal stress test."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from sim_id_fiskal.anchor import FiscalStressTest
from sim_id_fiskal.main import app

client = TestClient(app)


def test_pertamax_30pct_at_10pct_passthrough() -> None:
    res = FiscalStressTest().apply(fuel="pertamax", shock_pct=30, as_of=date(2026, 6, 10))
    assert res.shock_pct == 30
    assert res.pass_through == 0.10
    assert res.monthly_inflation_impact_pct == 3.0  # 30 * 0.10


def test_pertalite_50pct_at_30pct_passthrough() -> None:
    res = FiscalStressTest().apply(fuel="pertalite", shock_pct=50, as_of=date(2026, 6, 10))
    assert res.pass_through == 0.30
    assert res.monthly_inflation_impact_pct == 15.0


def test_solar_with_latest_price() -> None:
    res = FiscalStressTest().apply(
        fuel="solar",
        shock_pct=20,
        as_of=date(2026, 6, 10),
        latest_solar_idr_per_liter=6800,
    )
    assert "6,800" in res.notes
    assert "8,160" in res.notes
    assert res.monthly_inflation_impact_pct == 4.0  # 20 * 0.20


def test_unknown_fuel_raises() -> None:
    with pytest.raises(ValueError, match="Unknown fuel"):
        FiscalStressTest().apply(fuel="avtur", shock_pct=10, as_of=date(2026, 6, 10))


def test_health_endpoint() -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ask_endpoint_pertamax_30pct() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?",
            "fuel": "pertamax",
            "shock_pct": 30,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["monthly_inflation_impact_pct"] == 3.0
    assert "pertamax" in body["result"]["notes"].lower()


def test_ask_endpoint_unknown_fuel_400() -> None:
    r = client.post(
        "/ask",
        json={"question": "x", "fuel": "avtur", "shock_pct": 10},
    )
    assert r.status_code == 400
