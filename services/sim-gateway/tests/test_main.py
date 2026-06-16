"""Tests for sim-gateway."""

from __future__ import annotations

import time

import httpx
import jwt
import respx
from fastapi.testclient import TestClient

from sim_gateway.main import GATEWAY_JWT_SECRET, SCENARIO_TO_URL, app

client = TestClient(app)


def _token(sub: str = "tester") -> str:
    return jwt.encode(
        {
            "sub": sub,
            "iat": int(time.time()),
            "aud": "santara-gateway",
            "iss": "santara",
        },
        GATEWAY_JWT_SECRET,
        algorithm="HS256",
    )


def test_healthz() -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_agent_card_has_all_three_skills() -> None:
    r = client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Santara Gateway"
    skill_ids = {s["id"] for s in body["skills"]}
    assert skill_ids == {"ask_fiskal", "ask_politik", "ask_iklim"}


def test_a2a_no_bearer_401() -> None:
    r = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": "1", "method": "ask", "params": {"question": "x"}},
    )
    assert r.status_code == 401


def test_a2a_bad_bearer_401() -> None:
    r = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": "1", "method": "ask", "params": {"question": "x"}},
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert r.status_code == 401


def test_a2a_method_not_found() -> None:
    token = _token()
    r = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": "1", "method": "frobnicate", "params": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"]["code"] == -32601


def test_a2a_missing_question() -> None:
    token = _token()
    r = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": "1", "method": "ask", "params": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"]["code"] == -32602


def test_a2a_unknown_scenario() -> None:
    token = _token()
    r = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "ask",
            "params": {"question": "x", "scenario": "unknown_scenario"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"]["code"] == -32602
    assert "Unknown scenario" in body["error"]["message"]


def test_a2a_routes_to_fiskal() -> None:
    token = _token()
    fiskal_url = SCENARIO_TO_URL["pertamax_30pct"]
    with respx.mock(base_url=fiskal_url) as mock:
        mock.post("/ask").mock(
            return_value=httpx.Response(
                200,
                json={
                    "question": "Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?",
                    "result": {
                        "scenario": "pertamax_30pct",
                        "shock_pct": 30.0,
                        "monthly_inflation_impact_pct": 3.0,
                        "notes": "Latest Pertamax price: 12,300 IDR/liter. Shock +30% gives 15,990 IDR/liter. At pass-through 10%, the implied monthly inflation impact is 3.00 percentage points.",
                    },
                },
            )
        )
        r = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "ask",
                "params": {
                    "question": "Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?",
                    "scenario": "pertamax_30pct",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["details"]["monthly_inflation_impact_pct"] == 3.0
    assert "Pertamax" in body["result"]["answer"]


def test_a2a_routes_to_politik() -> None:
    token = _token()
    politik_url = SCENARIO_TO_URL["mbg_swing_voter_2029"]
    with respx.mock(base_url=politik_url) as mock:
        mock.post("/ask").mock(
            return_value=httpx.Response(
                200,
                json={
                    "question": "Apa dampak MBG terhadap swing voter di 2029?",
                    "result": {
                        "scenario": "mbg_swing_voter_2029",
                        "swing_change_pp": 5.6,
                        "direction": "gain",
                        "notes": "MBG coverage 80% with satisfaction 70% on base swing rate 10% implies 5.60pp swing voter change. Direction: gain. Confidence: high.",
                    },
                },
            )
        )
        r = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "ask",
                "params": {
                    "question": "Apa dampak MBG terhadap swing voter di 2029?",
                    "scenario": "mbg_swing_voter_2029",
                    "mbg_coverage_pct": 80,
                    "satisfaction_score": 70,
                    "base_swing_rate_pct": 10,
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["details"]["swing_change_pp"] == 5.6
    assert "5.60pp" in body["result"]["answer"]


def test_a2a_routes_to_iklim() -> None:
    token = _token()
    iklim_url = SCENARIO_TO_URL["karhutla_riau_haze"]
    with respx.mock(base_url=iklim_url) as mock:
        mock.post("/ask").mock(
            return_value=httpx.Response(
                200,
                json={
                    "question": "Kapan karhutla Riau menjadi krisis haze lintas batas?",
                    "result": {
                        "scenario": "karhutla_riau_haze",
                        "haze_index": 900.0,
                        "is_cross_border_crisis": True,
                        "days_to_crisis": 0,
                        "notes": "Haze index 900 from 100 hotspots, 30 km/h wind, 30 dry days. Already in cross-border haze crisis.",
                    },
                },
            )
        )
        r = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "ask",
                "params": {
                    "question": "Kapan karhutla Riau menjadi krisis haze lintas batas?",
                    "scenario": "karhutla_riau_haze",
                    "hotspots": 100,
                    "wind_speed_kmh": 30,
                    "dry_days": 30,
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["details"]["haze_index"] == 900.0
    assert body["result"]["details"]["is_cross_border_crisis"] is True
    assert "cross-border haze crisis" in body["result"]["answer"]


def test_a2a_downstream_validation_502() -> None:
    """When downstream returns 422, gateway returns 502 to the A2A caller.

    The gateway never echoes downstream 4xx. The A2A protocol wraps
    downstream errors as JSON-RPC internal error (-32603) with
    HTTP 502. The caller sees a uniform contract regardless of
    which downstream service failed and why.
    """
    token = _token()
    fiskal_url = SCENARIO_TO_URL["pertamax_30pct"]
    with respx.mock(base_url=fiskal_url) as mock:
        mock.post("/ask").mock(
            return_value=httpx.Response(
                422,
                json={"detail": "shock_pct must be between -100 and 200"},
            )
        )
        r = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "ask",
                "params": {
                    "question": "x",
                    "scenario": "pertamax_30pct",
                    "shock_pct": 300,
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 502
    body = r.json()
    assert body["error"]["code"] == -32603
    assert "422" in body["error"]["message"]
