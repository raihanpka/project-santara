"""Stub for the gRPC contracts package.

After the protobuf is generated, the generated Python stubs go here.
Until then, this module exposes a single helper that lets other code
detect whether the stubs are available, so the build script and tests
can degrade gracefully.
"""

from __future__ import annotations

from pathlib import Path

_PROTO_DIR = Path(__file__).resolve().parent.parent.parent.parent / "proto"


def proto_path() -> Path:
    return _PROTO_DIR / "simulation.proto"


def stubs_available() -> bool:
    return (_PROTO_DIR / "simulation_pb2.py").exists() and (
        _PROTO_DIR / "simulation_pb2_grpc.py"
    ).exists()
