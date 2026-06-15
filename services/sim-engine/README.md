# sim-engine

Go layer of the Project Santara simulation platform. Runs the actual tick loop for agent-based simulation. Receives work over gRPC from the Python services in `services/sim-id-*/`.

## Status

Scaffold. Phase 0 deliverable per [docs/ROADMAP.md](../../docs/ROADMAP.md). To be built from scratch. The legacy `apps/sim-engine/` code (under the old `github.com/santara/sim-engine` module) has been removed in this reset.

## Planned Layout

```
sim-engine/
+-- cmd/
|   +-- server/
|       +-- main.go
+-- internal/
|   +-- domain/         Agent, Market, Region, tick effects
|   +-- app/            use cases, tick engine, worker pool
|   +-- adapters/
|   |   +-- grpc/       gRPC server (the public surface)
|   |   +-- state/      in-memory state repositories
|   +-- ports/          gRPC handler definitions
+-- test/
+-- go.mod
+-- go.sum
+-- README.md
+-- Dockerfile
```

## Planned Responsibilities

- Tick loop: per-tick effects (hunger, health, supply, demand, prices)
- Worker pool: concurrent agent processing
- In-memory state: fast, zero-allocation hot loop
- gRPC server: receives simulation requests from Python services
- Outbox relay: optional, for hybrid event publishing

## What It Does Not Do

- HTTP serving. The Python services handle HTTP.
- LLM calls. The Python services handle LLM reasoning.
- Database I/O. In-memory only in v1.0. PostgreSQL via pgx planned for v1.5.0.
- Authentication. Auth happens at the gateway.

## Dependencies

- `google.golang.org/grpc` (gRPC server)
- `google.golang.org/protobuf` (protobuf runtime)
- `github.com/rs/zerolog` (structured logging)
- `github.com/google/uuid` (entity IDs)
- `github.com/caarlos0/env/v11` (env config)

## Port

Default 50052 (gRPC only).

## Test

The integration test in `apps/ai-engine/tests/test_integration.py` exercises the Go tick engine end to end. That test was the proof of concept for the old code. For the new code, the equivalent integration test will be added under `services/sim-engine/test/integration/`.
