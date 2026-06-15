# sim-id-fiskal

Indonesia fiscal stress test service. Answers questions about inflation, BI rate shocks, BBM price changes, subsidi allocation, and currency impact on household welfare.

## Status

In development. Phase 1 deliverable per [docs/ROADMAP.md](../../docs/ROADMAP.md). The first anchor problem in v0.1.0.

## Planned Layout

```
sim-id-fiskal/
+-- src/
|   +-- sim_id_fiskal/
|       +-- main.py
|       +-- agents/         HouseholdAgent, MarketAgent, GovernmentAgent, BankIndonesiaAgent
|       +-- scenarios/      pertamax_hike, bi_rate, subsidi_cut, currency_shock
|       +-- data/           BPS, BI, Bapanas fetchers
|       +-- mcp/            MCP tools
|       +-- a2a/            A2A endpoints
|       +-- grpc/           sim-engine gRPC client
|       +-- config.py
+-- tests/
+-- pyproject.toml
+-- README.md
+-- Dockerfile
```

## Anchor Problem 1

"Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?"

## Data Sources

- Bank Indonesia (BI rate, kurs, intervensi)
- Bapanas PIHPS (harga pangan harian)
- DJBC bea cukai (subsidi tracker)
- BPS inflasi series

See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) section 16 for the curated dataset plan.

## Dependencies

- `sim-kernel`
- `fastapi`, `pydantic-ai`, `pydantic`
- `asyncpg` for PostgreSQL
- `redis` for events
- `grpc` Python stubs (generated from `libs/rpc-contracts/`)

## Port

Default 8001.
