# Changelog

All notable changes to Project Santara are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/).

The English version of this file is canonical. The Bahasa Indonesia version lives in [docs-id/CHANGELOG.md](./docs-id/CHANGELOG.md) and is updated on the same commits as the English version. If the two diverge, the English version wins.

## [Unreleased]

No entries yet. The first entry will be the v0.1.0 milestone when `sim-kernel` modules, the `sim-engine` tick loop, `sim-gateway`, and `sim-id-fiskal` are implemented.

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
