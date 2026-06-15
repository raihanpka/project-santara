# sim-id-agraria

Indonesia agrarian micro-economy service. Models tengkulak distribution chains, Reforma Agraria scenarios, MBG supply chain, and farmer-versus-consumer welfare.

## Status

Planned for v1.0.0 per [docs/ROADMAP.md](../../docs/ROADMAP.md). Scaffold only.

## Planned Layout

```
sim-id-agraria/
+-- src/sim_id_agraria/
|   +-- main.py
|   +-- agents/         FarmerAgent, TengkulakAgent, ConsumerAgent, CooperativeAgent
|   +-- scenarios/      tengkulak_chain, reforma_agraria, mbg_supply
|   +-- data/           satudata.pertanian.go.id, food systems dashboard
|   +-- mcp/
|   +-- a2a/
|   +-- grpc/
+-- tests/
+-- pyproject.toml
+-- README.md
+-- Dockerfile
```

## Anchor Problem 4

"Koperasi Desa Merah Putih vs tengkulak, mana yang lebih tinggi kesejahteraannya?"

## Data Sources

- satudata.pertanian.go.id
- Food Systems Dashboard (FAO)
- BPS Sensus Pertanian 2023
- KPA agrarian conflict reports

## Dependencies

- `sim-kernel`
- `fastapi`, `pydantic-ai`, `pydantic`
- `asyncpg`, `redis`
- `grpc` stubs

## Port

Default 8004.
