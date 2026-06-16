# Changelog

All notable changes to Project Santara are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/).

The English version of this file is canonical. The Bahasa Indonesia version lives in [docs-id/CHANGELOG.md](./docs-id/CHANGELOG.md) and is updated on the same commits as the English version. If the two diverge, the English version wins.

## [Unreleased]

No entries yet. The next entry will be the v0.3.0 milestone when `sim-engine` runs a real tick (not a counter) and the sim-id services have real models with citations instead of pass-through placeholders.

## [0.2.0] - 2026-06-16

### Summary

Phase 2 ships the second and third anchor services (sim-id-politik for the MBG swing voter question, sim-id-iklim for the karhutla haze question), a scenario-based router in the gateway, Codecov integration, and several CI and Docker fixes that were caught by the release smoke test. The pass-through formulas are placeholders with citations needed, not real models (see Known limitations).

### Added

- **sim-id-politik**: pass-through political dynamics, `coverage * satisfaction * base_swing / 10000`. 12 tests pass, 95% line coverage.
- **sim-id-iklim**: pass-through climate emergency, `hotspots * wind_speed_kmh * dry_days / 100`. Cross-border crisis threshold at haze index 500. 15 tests pass, 98% line coverage.
- **Gateway scenario routing**: `Scenario` enum with `pertamax_30pct`, `mbg_swing_voter_2029`, `karhutla_riau_haze`. `SCENARIO_TO_URL` map. The AgentCard lists 3 skills.
- **Gateway HTTP status codes**: 400 for client errors (unknown scenario, missing question, unknown method), 502 for downstream service failures. The JSON-RPC error body is preserved for protocol-level handling.
- **Gateway JWT validation**: HS256 with `aud` and `iss` enforced. `exp` enforced by default. A startup warning is logged when the dev default secret is in use.
- **Docker Compose healthchecks**: every Python service has a `urllib`-based healthcheck. The gateway waits for all three sim-id services to be healthy via `depends_on.condition: service_healthy`. The sim-engine gRPC healthcheck is downgraded to a TCP probe because `grpc_health_probe` is not in the Alpine image.
- **Codecov integration**: `codecov.yml` at the repo root with monorepo flags (`python` and `go`). `require_ci_to_pass: false` so a Codecov outage does not break CI. Upload runs only on `main` (`if: github.ref == 'refs/heads/main'`).
- **GHCR namespace fix**: image tags changed from `ghcr.io/raihanpka/sim-engine` to `ghcr.io/raihanpka/project-santara/sim-engine` so the package lives under the repo's namespace, not a separate user-level package.
- **CI workflow rename**: `validate` renamed to `CI`.
- **Makefile cleanup**: `clean-act` target clears `~/.cache/act/`, `~/.cache/actcache/`, and Docker prune. `coverage` target installs `pytest-cov` via `uv pip install` (the venvs do not have a `pip` binary).
- **`.dockerignore`**: filters dev-only files (tests, `.venv`, generated stubs, docs, datasets) from the container image build context.

### Changed

- `services/sim-engine/go.mod` module path changed from `github.com/raihanpka/sim-engine` to `github.com/raihanpka/project-santara/services/sim-engine` so the Go module lives under the repo, not a separate user-level repo. All 5 Go source files updated. Go build and 4 Go tests still pass.
- Go test step in CI split into `Test Go with race` (no coverage) and `Test Go with coverage` (no race, `set` mode). The coverage step adds `GOTOOLDIR` to `PATH` because the `setup-go` image does not include `covdata` on the default path.

### Fixed

- `lint` and `test` jobs now iterate over all 5 Python services (politik and iklim were missing from the v0.1.0 CI loops).
- `cache-dependency-path: services/sim-engine/go.sum` added to both `Set up Go` steps. Without it, the cache step looked for `go.sum` at the repo root.
- v0.1.0 tag push never triggered the workflow because the `on:` section did not include `tags:`. Added `tags: ['v*']` under `push:`. The container-images job now actually fires on tag pushes.

### Known limitations

- The pass-through formulas in sim-id-politik and sim-id-iklim have magic numbers (10000, 500, 100) with no real citation. They are placeholders. A future version must replace them with real models with citations.
- The Go tick engine is still a counter, not a simulation. The `Run` RPC increments `tick` by `count`. Real tick logic is gated on benchmarks.
- The new sim-id services re-implement their own Pydantic request/response models instead of using `sim-kernel.models` types. A future version must wire them through sim-kernel so the wire format is shared.
- The gateway scenario map is hardcoded. Adding a fourth scenario requires editing three files (the enum, the map, the AgentCard, the test). A future version should use a registered handler interface.
- sim-id services have no authentication. They are reachable from the gateway only by network topology. A future version must add a shared-secret or mTLS check.
- No distributed tracing, no Prometheus metrics, no OpenTelemetry in the Python services. The Go service uses zerolog but the Python services print to stdout.
- `sim-id-fiskal` does not yet read from the curated `indonesia-fiscal-pressure` dataset. A future version must wire the model to the latest Pertamax price from the dataset.
- The Codecov upload only runs on `main`. Pull requests do not get coverage feedback yet.

### Test Results (v0.2.0)

- sim-kernel: 21 tests pass, 88% line coverage
- sim-id-fiskal: 7 tests pass
- sim-gateway: 10 tests pass (up from 7 in v0.1.0)
- sim-id-politik: 12 tests pass, 95% line coverage
- sim-id-iklim: 15 tests pass, 98% line coverage
- sim-engine (Go): 4 tests pass

Total: 69 tests across 6 packages. The Python integration test against the Go binary still passes.

[0.2.0]: https://github.com/raihanpka/project-santara/releases/tag/v0.2.0

## [0.1.0] - 2026-06-16

### Summary

The v0.1.0 entry marks the first working release of Project Santara. The Python intelligence tier and the Go performance tier are both built, tested, and wired together. The first anchor problem (Pertamax 30 percent shock) is answered end to end: a user sends an A2A JSON-RPC request to `sim-gateway`, the gateway forwards the question to `sim-id-fiskal` over HTTP, and the fiscal model returns a structured result. The Go tick engine accepts the same shock over gRPC, stores it in the simulation's macro indicators, and serves the updated world state.

This is pre-alpha software. The simulation models are deliberately simple. The tick engine counts, it does not simulate. The political, climate, and agrarian services are still scaffolds. The dataset pipeline is built and published. The Docker Compose stack is wired. The CI workflow runs on every push.

### Added

- `libs/sim-kernel/` full implementation. Nine modules: `models` (Pydantic v2 domain types), `events` (event envelopes, outbox pattern), `errors` (typed exception hierarchy), `locales` (id-JK, id-JB, id-JT, id-KI, id-SU, id-BA, en-US), `telemetry` (structlog setup, OpenTelemetry hooks), `a2a` (AgentCard builder, JSON-RPC helpers), `mcp` (tool base, server base), `prompts` (system prompt templates, few-shot examples), `grpc_contracts` (shared gRPC types). Twenty-one tests pass, eighty-eight percent line coverage. Apache 2.0 license declared in `pyproject.toml`. Python 3.12 required.
- `services/sim-engine/` Go implementation. The `cmd/server/main.go` boots a gRPC server on port 50052 (configurable via `SIM_ENGINE_GRPC_ADDR`). The `internal/grpc/server.go` implements all nine RPCs from `libs/rpc-contracts/proto/simulation.proto`: `CreateSimulation`, `DestroySimulation`, `SpawnAgent`, `KillAgent`, `RunTicks`, `Pause`, `Resume`, `GetWorldState`, `ApplyShock`. The `internal/state/memory.go` holds simulations in a `map` guarded by a `sync.RWMutex` with separate locked and unlocked snapshot paths to avoid the non-reentrant RWMutex deadlock. The `internal/app/tick.go` runs the tick engine (v0.1.0 is a counter, gated on benchmarks proving the hot loop needs Go). The `internal/telemetry/logger.go` wraps zerolog. The `internal/config/config.go` reads environment variables. Four in-process tests pass using `bufconn`-free real TCP listeners on random ports. The `Dockerfile` is a multi-stage Alpine build.
- `services/sim-gateway/` Python implementation. FastAPI app with three endpoints: `GET /healthz` for liveness, `GET /.well-known/agent-card.json` for the A2A AgentCard, and `POST /a2a` for the A2A JSON-RPC entry. The `ask` method validates a JWT bearer token (`HS256`, `GATEWAY_JWT_SECRET` env var), forwards the question to `sim-id-fiskal` at `SIM_ID_FISKAL_URL`, and returns the result. Seven tests pass using `respx` to mock the downstream HTTP call. The `Dockerfile` is a `python:3.12-slim` build that installs via `uv`.
- `services/sim-id-fiskal/` Python implementation. The fiscal stress test that answers the first anchor question ("Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?"). The `anchor.py` module holds the pass-through fiscal model: Pertamax 10 percent pass-through, Pertalite 30 percent, Solar 20 percent. The `main.py` exposes `GET /healthz` and `POST /ask`. The endpoint validates the fuel name against a fixed allowlist (`{pertamax, pertalite, solar}`) and returns 400 for unknown fuels. Seven tests pass.
- `libs/rpc-contracts/proto/simulation.proto` written. Ten RPCs in one service, eleven messages including `Agent`, `FiscalShock`, `PoliticalShock`, `ClimateShock`, `AgrarianShock`, `Shock` (oneof over the four shock kinds), `WorldState`, and the request/response envelopes. `option go_package` set to `github.com/raihanpka/sim-engine/internal/grpc_gen;grpc_gen`.
- `libs/rpc-contracts/python/sim_rpc/` generated Python stubs. The `simulation_pb2.py` and `simulation_pb2_grpc.py` are produced by `grpc_tools.protoc`. The gRPC stub's import is patched to use the relative `from . import simulation_pb2` form so the stubs work as a package.
- `libs/rpc-contracts/python/tests/test_sim_engine_integration.py` written. The end-to-end check that proves the proto contract is satisfied on both sides. Starts the Go binary, connects over gRPC, exercises all nine RPCs, asserts responses. Five tests pass.
- `docker-compose.yml` at the repository root. Three services: `sim-engine` (Go gRPC on 50052), `sim-id-fiskal` (Python FastAPI on 8001), `sim-gateway` (Python FastAPI on 8000). The gateway depends on the fiscal service. Healthcheck on the gRPC service is documented as a future addition (the `grpc_health_probe` binary is not yet installed in the image).
- `.github/workflows/ci.yml` written. Two jobs: `python` (installs sim-kernel, sim-id-fiskal, sim-gateway, and rpc-contracts with `uv`, runs all Python tests, runs the Go integration test from Python) and `go` (builds and tests sim-engine with `go test -race`). Runs on push to `main` and on pull requests.
- `Makefile` updated. New targets: `engine-test` (Go tests only), `proto-py` (generate Python stubs, patch the gRPC import), `proto-go` (generate Go stubs, install plugins if missing). The `build-go` target now produces `bin/sim-engine-server`. The duplicate `dataset-build` / `dataset-push` shadowing bug from the v0.0.0 reset is fixed. Help text updated.
- `.python-version` at the repository root pins Python 3.12.13 for the whole monorepo. Each service still owns its own `uv` venv.
- `.gitignore` updated. Added Go binary entries (`*.exe`, `*.test`, `*.out`, `services/*/bin/`) and generated protobuf stub entries (Python and Go). The `.proto` files remain in version control.
- Root `README.md` updated. The "Current State" section now reflects v0.1.0 reality. The "Quick Start" section now includes the Docker Compose stack that exists. The "Core Services" status table is updated.

### Changed

- `services/sim-id-fiskal/pyproject.toml` fixed. The invalid `Topic :: Economics` classifier was removed (PyPI rejects it). The broken `sim-kernel @ { root = "..." }` reference was replaced with a proper relative path. The Python version requirement is `>=3.12` to match the kernel.
- `libs/sim-kernel/pyproject.toml` fixed. The `Topic :: Economics` classifier was removed. The `sim-kernel` package now lists `pydantic-settings` as a dependency for the telemetry module.
- `libs/sim-datasets/id_fiscal_pressure/build.py` updated. The `build_dataset` function now preserves the existing `dist/README.md` unless `--card` is passed. The `--card-only` flag regenerates the card only. The `Makefile` gets a new `dataset-card` target that runs `--card-only` for safe repeat use.

### Known Limitations (v0.1.0)

- The Go tick engine is a counter. It does not simulate. The `Run` RPC increments `tick` by `count`, the `ApplyShock` RPC stores the shock fields in the macro indicators map. The real tick logic (hunger, supply, demand, prices, agent decisions) is gated on benchmarks proving the Python intelligence tier cannot do it fast enough.
- The fiscal pass-through model is a single coefficient per fuel. It does not account for subsidi interactions, second-round effects, or exchange rate pass-through. The `BiRateChangeBps` field is stored but not yet connected to the inflation impact calculation.
- JWT validation in `sim-gateway` is a placeholder. The secret is read from an environment variable, the algorithm is `HS256`, and the only claim checked is signature validity. There is no audience, no issuer, no expiration enforcement, no key rotation.
- No persistent state. The Go engine stores simulations in memory. Process restart loses all simulations. PostgreSQL via `pgx` is planned for v1.5.0.
- No healthcheck on the gRPC service in the Docker image. The `docker-compose.yml` references `grpc_health_probe` but the binary is not yet installed in the `sim-engine` image.
- The Python integration test builds the Go binary on first run if it does not exist. CI pre-builds it. The development loop assumes `go` is on the PATH.
- The Hugging Face dataset (`raihanpka/indonesia-fiscal-pressure`) is published but not yet referenced from the runtime services. The data ingestion path from Hugging Face to `sim-id-fiskal` is planned for v0.2.0.

### Test Results (v0.1.0)

- `libs/sim-kernel`: 21 tests passed, 88% line coverage
- `services/sim-id-fiskal`: 7 tests passed
- `services/sim-gateway`: 7 tests passed
- `services/sim-engine` (Go): 4 tests passed
- `libs/rpc-contracts/python/tests/test_sim_engine_integration.py`: 5 tests passed
- Total: 44 tests across 5 packages

## [0.0.0] - 2026-06-15

### Summary

The v0.0.0 entry marks a full reset of the codebase. The previous structure (a TypeScript-first monorepo with Go and Python services under `apps/`, Nx as the build tool, and `infra/` for deployment manifests) was deleted. The new structure is a hybrid microservices layout under `services/` and `libs/`, with a fresh `sim-kernel` Python library, a fresh `sim-engine` Go service, and a new documentation set.

This is a one-time reset. It happened because the legacy architecture did not match the new goals: a library-first Python intelligence tier, a Go performance tier, and curated Hugging Face datasets. There is no v0.0.1 of the old code. The old code is gone, and the lessons learned are recorded in the new architecture and roadmap documents.

### Added

- `services/sim-engine/` scaffold with `go.mod` declaring `github.com/raihanpka/sim-engine` and a Go 1.22 toolchain. No Go code yet; the directory contains only the module file and a README that documents the planned layout (`cmd/server`, `internal/domain`, `internal/app`, `internal/adapters/state`, `internal/adapters/grpc`, `internal/telemetry`).
- `services/sim-gateway/` scaffold. Python A2A router, MCP server hub, JWT auth, optional WebSocket telemetry. README documents the planned layout. No `pyproject.toml` yet.
- `services/sim-id-fiskal/` scaffold. Indonesia fiscal stress test, the first anchor problem. README documents the planned layout. No `pyproject.toml` yet.
- `services/sim-id-politik/` scaffold. Indonesia political dynamics, the second anchor problem. README documents the planned layout. No `pyproject.toml` yet.
- `services/sim-id-iklim/` scaffold. Indonesia climate emergency, the third anchor problem. README documents the planned layout. No `pyproject.toml` yet.
- `services/sim-id-agraria/` scaffold. Indonesia agrarian micro-economy, the fourth anchor problem. README documents the planned layout. No `pyproject.toml` yet.
- `libs/sim-kernel/` scaffold. Shared Python library. Full `pyproject.toml` is published with Apache 2.0 declared, all optional dependency groups (`dev`, `mcp`, `grpc`, `docs`) defined, ruff and mypy configuration, pytest configuration, and a README that documents the module list (`models`, `events`, `a2a`, `mcp`, `locales`, `prompts`, `telemetry`, `errors`, `grpc_contracts`). Modules are not yet implemented.
- `libs/rpc-contracts/` scaffold. Empty directory with a README. Will hold the protobuf contracts for the gRPC boundary between Python services and the Go engine. No `.proto` files yet.
- Root `Makefile` with convenience targets: `help`, `install`, `test`, `test-py`, `test-go`, `test-kernel`, `lint`, `format`, `build-go`, `docker-up`, `docker-down`, `clean`. The Makefile is intentionally simple. It is not a monorepo build tool.
- `docs/COMMIT_STYLE.md` derived from the existing git history. Documents the Conventional Commits format, the type list, the scope list, the body conventions, the breaking-change marker, the revert format, and the merge-commit format.
- Root `RELEASE.md` defining the four distribution channels: PyPI for `sim-kernel`, GitHub Container Registry for Docker images, Hugging Face Hub for curated datasets, and GitHub Releases for the Go static binary. The release process is documented end to end, including pre-release, post-release, version compatibility, and channels not used.
- `docs/ARCHITECTURE.md` (22 KB). The canonical architecture document. Seventeen sections: philosophy, system overview, service map, repository layout, technology stack, data flow, cross-service communication, sim-kernel library specification, bilingual and locale support, persistence model, deployment, security model, performance targets, testing strategy, observability, architecture decision records, curated datasets. Mermaid diagrams replace ASCII art.
- `docs-id/ARCHITECTURE.md` (22 KB). Bahasa Indonesia mirror of `docs/ARCHITECTURE.md`.
- `docs-id/PANDUAN.md` (12 KB). Bahasa Indonesia front door for the project. Mirrors `README.md` in tone, depth, and section structure.
- Root `AGENTS.md` (this file plus the `AGENTS.md` companion). Guide for AI coding assistants. Hard rules, don'ts, bilingual policy, commit style, how to run, test, lint.
- Root `.gitignore` updated to reflect the new directory layout.

### Changed

- `README.md` rewritten (now 12 KB). Front door for the project. Thirteen sections: what is Santara, why it exists, current state, quick start, core services, use cases, architecture, tech stack, repository layout, documentation, contributing, license, citation. Mermaid diagram for the repository layout. Honest about the scaffold state.
- `CONTRIBUTING.md` updated to reference `docs/COMMIT_STYLE.md` and `RELEASE.md`. The contributor flow now includes "follow the commit style" and "follow the release process" as explicit steps.
- `CODE_OF_CONDUCT.md` updated to add a Bahasa Indonesia pledge paragraph and an explicit reference to non-English-speaking contributors.
- `SECURITY.md` updated. The supported versions table now lists the v0.0.0 reset and explicitly marks the legacy `apps/` code as unsupported.
- `Makefile` rewritten. The old Makefile was a 280-line Nx wrapper. The new Makefile is 124 lines of plain shell. It is not a build orchestrator; it is a convenience layer.

### Removed

- `apps/ai-engine/` and all of its subdirectories. The Python FastAPI code, the Neo4j client, the agentic RAG implementation, the graph pruning engine, the LLM router, the integration tests, and the configuration files are all gone. The lessons learned are recorded in `docs/ARCHITECTURE.md` and in the Phase 1 roadmap.
- `apps/sim-engine/` and all of its subdirectories. The Go DDD code, the tick engine, the gRPC server, the in-memory state adapter, and the build artifacts are all gone. The new Go service is being scaffolded fresh under `services/sim-engine/` with a new module name.
- `apps/frontend/` and all of its subdirectories. The TypeScript frontend was not part of the new architecture. The optional sim-dashboard is planned as a Phase 3 deliverable.
- `infra/` and all of its subdirectories. The old infrastructure-as-code was tied to the old monorepo. New infrastructure is planned as part of Phase 1.
- `libs/` from the legacy tree, including any old shared code. The new `libs/` is empty except for `sim-kernel/` and `rpc-contracts/`.
- `.nx/`, `nx.json`, `package.json`, `bun.lock`, and all other Nx configuration files. The project does not use a monorepo build tool in v1.0.
- The `.docs/` directory. The English documentation now lives at `docs/` and the Bahasa Indonesia documentation lives at `docs-id/`.

### License Note

The new code under `services/`, `libs/`, `docs/`, and the root documentation files is licensed under Apache License 2.0. The `LICENSE` file at the repository root was updated from the legacy GNU GPL 3.0 text to the full Apache 2.0 text as part of this reset. Apache 2.0 is now the authoritative license for the entire repository. The `pyproject.toml` and `go.mod` files in the new code continue to declare Apache 2.0, and the `docs/ROADMAP.md` open question OQ-0001 (whether to update the LICENSE file) is now resolved.

### Migration Notes

There is no migration path from the legacy codebase to the new one. The legacy code is gone. If you have local branches, pull requests, or issues that reference the old paths, please reopen them against the new paths:

- `apps/ai-engine/` -> `services/sim-id-fiskal/`, `services/sim-gateway/`, or `libs/sim-kernel/`, depending on the code.
- `apps/sim-engine/` -> `services/sim-engine/`.
- `apps/frontend/` -> `services/sim-dashboard/` (Phase 3, not yet scaffolded).
- `infra/` -> `docker-compose.yml` at the repository root (planned, not yet authored).
- `.docs/AGENTS.md` -> `docs/AGENTS.md` (further moved to docs/ for project organization).
- `.docs/DEVELOPMENT.md` -> `docs/ROADMAP.md` and `CONTRIBUTING.md`.

[0.0.0]: https://github.com/raihanpka/project-santara/releases/tag/v0.0.0
