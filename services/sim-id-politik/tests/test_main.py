"""Tests for sim-id-politik FastAPI app."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sim_id_politik.main import app

client = TestClient(app)


def test_healthz() -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ask_endpoint_mbg_swing_voter_2029() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "Apa dampak MBG terhadap swing voter di 2029?",
            "scenario": "mbg_swing_voter_2029",
            "mbg_coverage_pct": 80,
            "satisfaction_score": 70,
            "base_swing_rate_pct": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["swing_change_pp"] == 5.6
    assert body["result"]["direction"] == "gain"
    assert "5.60pp" in body["result"]["notes"]


def test_ask_endpoint_unknown_scenario_400() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "x",
            "scenario": "unknown_scenario",
            "mbg_coverage_pct": 50,
            "satisfaction_score": 50,
            "base_swing_rate_pct": 10,
        },
    )
    assert r.status_code == 400


def test_ask_endpoint_invalid_coverage_400() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "x",
            "scenario": "mbg_swing_voter_2029",
            "mbg_coverage_pct": 150,
            "satisfaction_score": 50,
            "base_swing_rate_pct": 10,
        },
    )
    assert r.status_code == 422
