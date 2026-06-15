# sim-id-politik

Indonesia political dynamics service. Models kabinet reshuffle, demo propagation, electoral coalition shifts, and public sentiment response to policy events.

## Status

Planned for v0.5.0 per [docs/ROADMAP.md](../../docs/ROADMAP.md). Scaffold only.

## Planned Layout

```
sim-id-politik/
+-- src/sim_id_politik/
|   +-- main.py
|   +-- agents/         PoliticianAgent, PartyAgent, VoterAgent, MediaAgent
|   +-- scenarios/      reshuffle, demo_propagation, swing_voter
|   +-- data/           polling aggregators, news feeds
|   +-- mcp/
|   +-- a2a/
|   +-- grpc/
+-- tests/
+-- pyproject.toml
+-- README.md
+-- Dockerfile
```

## Anchor Problem 2

"Apa dampak MBG terhadap swing voter di 2029?"

## Data Sources

- Poltracking, LSI, SMRC polling
- BEM UI statements
- Regional political events
- Historical election results (KPU)

## Dependencies

- `sim-kernel`
- `fastapi`, `pydantic-ai`, `pydantic`
- `asyncpg`, `redis`
- `grpc` stubs

## Port

Default 8002.
