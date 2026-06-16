"""Integration test: full flow from gateway to sim-id-fiskal.

This test exercises the real sim-id-fiskal FastAPI app under
TestClient, with a real fiskal request that includes fuel
price lookup. It does not start a real HTTP server; it uses
FastAPI's TestClient, which runs the app in-process.

For end-to-end tests that span gateway + fiskal, see
tests/test_main.py which uses respx to mock the downstream
HTTP call. This file is the unit-level integration for
sim-id-fiskal: it confirms the dataset loader, the engine,
and the FastAPI request handling all chain together.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from sim_id_fiskal.main import app

client = TestClient(app)


def _write_fake_dataset(path: Path) -> None:
    rows = [
        {
            "date": "2026-06-01",
            "indicator": "PERTAMAX_IDR_PER_LITER",
            "region": "IDN",
            "value": 12500.0,
            "unit": "IDR_per_liter",
            "source_id": "esdm.pertamina.retail",
        },
    ]
    pd.DataFrame(rows).to_parquet(path)


def test_ask_uses_dataset_when_no_latest_supplied(
    tmp_path: Path, monkeypatch
) -> None:
    """When the caller omits latest_fuel_idr_per_liter, the service
    reads it from the dataset. The response notes should reflect
    the dataset value, not a missing-price fallback.
    """
    from sim_id_fiskal import main as fiskal_main

    dataset = tmp_path / "fake.parquet"
    _write_fake_dataset(dataset)
    monkeypatch.setattr(fiskal_main, "DATASET_PATH", dataset)

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
    assert "12,500" in body["result"]["notes"]
    assert "16,250" in body["result"]["notes"]  # 12500 * 1.30


def test_ask_caller_supplied_price_overrides_dataset(
    tmp_path: Path, monkeypatch
) -> None:
    """When the caller supplies latest_fuel_idr_per_liter, the dataset
    is not consulted. The response notes should reflect the caller
    value.
    """
    from sim_id_fiskal import main as fiskal_main

    dataset = tmp_path / "fake.parquet"
    _write_fake_dataset(dataset)
    monkeypatch.setattr(fiskal_main, "DATASET_PATH", dataset)

    r = client.post(
        "/ask",
        json={
            "question": "x",
            "fuel": "pertamax",
            "shock_pct": 30,
            "latest_fuel_idr_per_liter": 20000,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "20,000" in body["result"]["notes"]


def test_ask_missing_dataset_falls_back_to_numeric_only(
    tmp_path: Path, monkeypatch
) -> None:
    """When the dataset is missing and the caller supplied no price,
    the response is a numeric shock report (no IDR/liter figure).
    """
    from sim_id_fiskal import main as fiskal_main

    monkeypatch.setattr(
        fiskal_main,
        "DATASET_PATH",
        tmp_path / "does-not-exist.parquet",
    )

    r = client.post(
        "/ask",
        json={
            "question": "x",
            "fuel": "pertamax",
            "shock_pct": 30,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["monthly_inflation_impact_pct"] == 3.0
    assert "Latest fuel price not supplied" in body["result"]["notes"]


def test_ask_validates_shock_pct_with_422() -> None:
    r = client.post(
        "/ask",
        json={"question": "x", "fuel": "pertamax", "shock_pct": 300},
    )
    assert r.status_code == 422


def test_ask_validates_missing_question_with_422() -> None:
    r = client.post(
        "/ask",
        json={"fuel": "pertamax", "shock_pct": 30},
    )
    assert r.status_code == 422


def test_ask_unknown_fuel_returns_400() -> None:
    r = client.post(
        "/ask",
        json={"question": "x", "fuel": "avtur", "shock_pct": 30},
    )
    assert r.status_code == 400
