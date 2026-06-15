# sim-gateway

A2A router, MCP server hub, JWT auth, optional WebSocket telemetry. Public HTTP entry point for the simulation platform.

## Status

In development. Phase 1 deliverable per [docs/ROADMAP.md](../../docs/ROADMAP.md).

## Planned Layout

```
sim-gateway/
+-- src/
|   +-- sim_gateway/
|       +-- main.py
|       +-- api/             FastAPI routers
|       +-- auth/            JWT verification
|       +-- a2a/             A2A client and router
|       +-- mcp/             MCP server hub
|       +-- ws/              optional WebSocket telemetry
|       +-- config.py
+-- tests/
+-- pyproject.toml
+-- README.md
+-- Dockerfile
```

## Planned Endpoints

- `GET /health`, `GET /health/ready`
- `POST /a2a/v1/message/send` (A2A protocol)
- `GET /a2a/v1/agent-card` (static Agent Card)
- `POST /mcp/v1/tools/list`, `POST /mcp/v1/tools/call` (MCP protocol)
- `WS /ws/v1/scenarios/{id}/stream` (optional, v1.0)
- `POST /v1/scenarios` (top-level scenario launcher)

## Dependencies

- `sim-kernel` (the shared library)
- `fastapi`, `uvicorn`, `pydantic`, `pydantic-ai`
- `httpx` for inter-service calls
- `redis` for the event bus
- `pyjwt` for JWT verification

## Port

Default 8000.
