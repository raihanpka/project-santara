# sim-id-iklim

Indonesia climate emergency service. Models El Nino projection, karhutla cascade, banjir response, and food production impact on padi.

## Status

Planned for v0.5.0 per [docs/ROADMAP.md](../../docs/ROADMAP.md). Scaffold only.

## Planned Layout

```
sim-id-iklim/
+-- src/sim_id_iklim/
|   +-- main.py
|   +-- agents/         WeatherAgent, FireAgent, FloodAgent, FarmerAgent
|   +-- scenarios/      el_nino, karhutla_cascade, banjir_response
|   +-- data/           BMKG, BNPB, KLHK SiPongi, NOAA fetchers
|   +-- mcp/
|   +-- a2a/
|   +-- grpc/
+-- tests/
+-- pyproject.toml
+-- README.md
+-- Dockerfile
```

## Anchor Problem 3

"Kapan karhutla Riau menjadi krisis haze lintas batas?"

## Data Sources

- BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)
- BNPB (Badan Nasional Penanggulangan Bencana)
- KLHK SiPongi (hotspot monitoring)
- NOAA (climate forecasts)
- FAO FAOSTAT (production impact)

## Dependencies

- `sim-kernel`
- `fastapi`, `pydantic-ai`, `pydantic`
- `asyncpg`, `redis`
- `grpc` stubs

## Port

Default 8003.
