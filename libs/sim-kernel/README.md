# sim-kernel

The shared Python library at the heart of the Project Santara simulation platform. Every Python service in `services/` imports this library. The Go service in `services/sim-engine/` does not import it; the two tiers communicate over gRPC.

## Status

Scaffold. Phase 1 deliverable per [docs/ROADMAP.md](../../docs/ROADMAP.md). Package metadata is published; the actual modules are not yet implemented.

## Planned Modules

```
sim-kernel/
+-- src/
|   +-- sim_kernel/
|       +-- __init__.py
|       +-- models.py         Pydantic models: Agent, Market, Region, Event, FiscalShock, PoliticalShock, ClimateShock
|       +-- events.py         event envelope, outbox helpers
|       +-- a2a.py            AgentCard generator, A2A client, A2A server base
|       +-- mcp.py            MCPServerBase, tool decorator, JSON schema helpers
|       +-- locales.py        locale presets for ID, US, IN, PH
|       +-- prompts.py        system prompt templates
|       +-- telemetry.py      OpenTelemetry helpers
|       +-- errors.py         standard error slugs
|       +-- grpc_contracts/   Python stubs generated from libs/rpc-contracts/
+-- tests/
+-- pyproject.toml
+-- README.md
```

## Design Rules

- **No I/O.** Every function in sim-kernel is pure or accepts its dependencies as arguments. The library does not connect to a database, network, or filesystem.
- **No business logic.** sim-kernel defines types, events, and protocol helpers. It does not contain domain logic. The services contain the domain logic.
- **Pydantic v2 only.** All data models are Pydantic. No dataclasses, no attrs.
- **Type hints on every public function.** Strict mode is on.
- **Async by default.** Public functions that touch I/O are `async def`. Public functions that do not are `def`.

## Versioning

sim-kernel follows Semantic Versioning strictly.

- Breaking change to a public model = major version bump
- New model or new public function = minor version bump
- Bug fix or documentation update = patch version bump

Services pin to a minor version range, never a major range.

## Install

```
pip install sim-kernel
```

## Develop

```
pip install -e ".[dev]"
pytest
```

## Distribution

- PyPI: `pip install sim-kernel` (target: v0.1.0)
- Source: this repository
- License: Apache 2.0
