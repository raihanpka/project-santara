"""Tests for sim-id-iklim FastAPI app."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sim_id_iklim.main import app

client = TestClient(app)


def test_healthz() -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ask_endpoint_karhutla_riau_haze_no_crisis() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "Kapan karhutla Riau menjadi krisis haze lintas batas?",
            "scenario": "karhutla_riau_haze",
            "hotspots": 30,
            "wind_speed_kmh": 15,
            "dry_days": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["haze_index"] == 45.0
    assert body["result"]["is_cross_border_crisis"] is False
    assert body["result"]["days_to_crisis"] > 0


def test_ask_endpoint_karhutla_riau_haze_crisis() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "Kapan karhutla Riau menjadi krisis haze lintas batas?",
            "scenario": "karhutla_riau_haze",
            "hotspots": 100,
            "wind_speed_kmh": 30,
            "dry_days": 30,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["haze_index"] == 900.0
    assert body["result"]["is_cross_border_crisis"] is True
    assert body["result"]["days_to_crisis"] == 0


def test_ask_endpoint_unknown_scenario_400() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "x",
            "scenario": "unknown_scenario",
            "hotspots": 10,
            "wind_speed_kmh": 10,
            "dry_days": 5,
        },
    )
    assert r.status_code == 400


def test_ask_endpoint_invalid_hotspots_400() -> None:
    r = client.post(
        "/ask",
        json={
            "question": "x",
            "scenario": "karhutla_riau_haze",
            "hotspots": -1,
            "wind_speed_kmh": 10,
            "dry_days": 5,
        },
    )
    assert r.status_code == 422
