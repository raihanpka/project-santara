"""Python integration test for sim-engine.

Starts the Go sim-engine binary, connects over gRPC, exercises all 9 RPCs,
asserts responses. This is the canonical end-to-end check that the
proto contract is satisfied on both sides.

ponytail: subprocess + grpc.insecure_channel. No docker, no flake.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import grpc
import pytest

_PYTHON_DIR = Path(__file__).resolve().parent.parent
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from sim_rpc import simulation_pb2 as pb  # noqa: E402
from sim_rpc import simulation_pb2_grpc as pb_grpc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[4]
GO_BINARY = REPO_ROOT / "services" / "sim-engine" / "bin" / "sim-engine-server"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_listen(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f"server did not start listening on port {port} within {timeout_s}s")


def _ensure_binary() -> Path:
    """Build the Go binary if it does not exist."""
    if GO_BINARY.exists():
        return GO_BINARY
    GO_BINARY.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["go", "build", "-o", str(GO_BINARY), "./cmd/server"],
        cwd=str(REPO_ROOT / "services" / "sim-engine"),
        check=True,
    )
    return GO_BINARY


@pytest.fixture(scope="module")
def engine():
    if shutil.which("go") is None:
        pytest.skip("go toolchain not available")
    if not _ensure_binary().exists() and shutil.which("go") is None:
        pytest.skip("go binary not built and go toolchain not available")
    _ensure_binary()
    port = _free_port()
    env = os.environ.copy()
    env["SIM_ENGINE_GRPC_ADDR"] = f"127.0.0.1:{port}"
    proc = subprocess.Popen(
        [str(GO_BINARY)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_listen(port)
        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield pb_grpc.SimulationServiceStub(channel)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_create_simulation(engine) -> None:
    r = engine.CreateSimulation(
        pb.CreateSimulationRequest(
            scenario_id="pertamax_30pct",
            locale="id-JK",
            seed=42,
            initial_state={"bi_rate_pct": 6.0, "pertamax_idr_pl": 12300.0},
        )
    )
    assert r.simulation_id
    assert r.initial_state.tick == 0
    assert r.initial_state.macro_indicators["bi_rate_pct"] == 6.0
    assert r.initial_state.macro_indicators["pertamax_idr_pl"] == 12300.0


def test_run_ticks_pause_resume(engine) -> None:
    r = engine.CreateSimulation(pb.CreateSimulationRequest(scenario_id="t", locale="id", seed=1))
    sid = r.simulation_id
    r1 = engine.RunTicks(pb.RunTicksRequest(simulation_id=sid, count=5))
    assert r1.final_state.tick == 5
    engine.Pause(pb.PauseRequest(simulation_id=sid))
    r2 = engine.RunTicks(pb.RunTicksRequest(simulation_id=sid, count=5))
    assert r2.final_state.tick == 5
    engine.Resume(pb.ResumeRequest(simulation_id=sid))
    r3 = engine.RunTicks(pb.RunTicksRequest(simulation_id=sid, count=3))
    assert r3.final_state.tick == 8


def test_spawn_kill_agent(engine) -> None:
    r = engine.CreateSimulation(pb.CreateSimulationRequest(scenario_id="t", locale="id", seed=1))
    sid = r.simulation_id
    ar = engine.SpawnAgent(
        pb.SpawnAgentRequest(
            simulation_id=sid, kind="household", locale="id-JK",
            initial_state={"income_idr": 5_000_000.0, "household_n": 4.0},
        )
    )
    assert ar.agent_id
    ws = engine.GetWorldState(pb.GetWorldStateRequest(simulation_id=sid))
    assert len(ws.agents) == 1
    engine.KillAgent(pb.KillAgentRequest(simulation_id=sid, agent_id=ar.agent_id))
    ws2 = engine.GetWorldState(pb.GetWorldStateRequest(simulation_id=sid))
    assert len(ws2.agents) == 0


def test_apply_fiscal_shock(engine) -> None:
    r = engine.CreateSimulation(pb.CreateSimulationRequest(scenario_id="t", locale="id", seed=1))
    sid = r.simulation_id
    ar = engine.ApplyShock(
        pb.ApplyShockRequest(
            shock=pb.Shock(
                simulation_id=sid,
                fiscal=pb.FiscalShock(
                    pertamax_price_change_pct=30.0,
                    bi_rate_change_bps=25.0,
                    subsidi_change_pct=-10.0,
                ),
            )
        )
    )
    assert ar.after_shock.macro_indicators["pertamax_price_change_pct"] == 30.0
    assert ar.after_shock.macro_indicators["bi_rate_change_bps"] == 25.0


def test_destroy_simulation(engine) -> None:
    r = engine.CreateSimulation(pb.CreateSimulationRequest(scenario_id="t", locale="id", seed=1))
    sid = r.simulation_id
    engine.DestroySimulation(pb.DestroySimulationRequest(simulation_id=sid))
    with pytest.raises(grpc.RpcError) as exc:
        engine.GetWorldState(pb.GetWorldStateRequest(simulation_id=sid))
    assert exc.value.code() == grpc.StatusCode.NOT_FOUND or exc.value.code() == grpc.StatusCode.UNKNOWN
