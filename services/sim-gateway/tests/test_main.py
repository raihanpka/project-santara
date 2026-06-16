"""Tests for sim-gateway."""

from __future__ import annotations

import time

import httpx
import jwt
import respx
from fastapi.testclient import TestClient

from sim_gateway.main import GATEWAY_JWT_SECRET, app

client = TestClient(app)


def _token(sub: str = "tester") -> str:
    return jwt.encode({"sub": sub, "iat": int(time.time())}, GATEWAY_JWT_SECRET, algorithm="HS256")


def test_healthz() -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_agent_card_path() -> None:
    r = client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Santara Gateway"
    assert any(s["id"] == "ask_fiskal" for s in body["skills"])


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


def test_a2a_forwards_to_fiskal() -> None:
    token = _token()
    with respx.mock(base_url="http://sim-id-fiskal:8001") as mock:
        mock.post("/ask").mock(
            return_value=httpx.Response(
                200,
                json={
                    "question": "Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?",
                    "result": {
                        "shock": "pertamax_price_+30pct",
                        "shock_pct": 30.0,
                        "pass_through": 0.10,
                        "monthly_inflation_impact_pct": 3.0,
                        "as_of": "2026-06-16",
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
                    "question": "Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?"
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["details"]["monthly_inflation_impact_pct"] == 3.0
    assert "Pertamax" in body["result"]["answer"]
