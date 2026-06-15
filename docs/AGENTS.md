# AGENTS.md

This file guides AI coding assistants (Claude, GPT, Cursor, Copilot, Aider, and similar) working inside the Project Santara repository. Read it fully before touching code. Following it saves your human reviewer time and reduces the chance of a rejected pull request.

## Table of Contents

1. Project Snapshot
2. What This Repository Is
3. Repository Layout
4. Architecture in One Page
5. The Go Service Is Not a Joke
6. Coding Style (Hard Rules)
7. Documentation Style
8. Commit and PR Style
9. Don'ts (Hard Blocks)
10. How to Run, Test, Lint
11. Bilingual Content
12. When You Are Unsure

## 1. Project Snapshot

- Name: Project Santara.
- Purpose: open-source simulation platform for Indonesia's economic, political, climatic, and agrarian systems.
- Form: hybrid microservices. Python intelligence tier, Go performance tier, shared Python library `sim-kernel`.
- Stage: pre-alpha (v0.0.0). The codebase is being rebuilt from scratch. The current tree is scaffold only.
- Owner: Raihan Putra Kirana.
- Repo: `github.com/raihanpka/project-santara`.
- License: Apache 2.0 (LICENSE file at the repository root).

## 2. What This Repository Is

- A simulation platform, not a chat product. The interesting work is running scenarios and returning grounded answers.
- A hybrid system. Python handles language-model reasoning, HTTP, A2A, MCP. Go handles the tick loop.
- An Indonesian-first project. Bahasa Indonesia is a first-class language, not a translation afterthought.
- A real open-source project. Apache 2.0 for the new code. Not "source available" with a separate commercial license.
- A local-first project. `docker compose up` is the demo. Cloud is opt-in.

It is not:

- A monorepo with a build tool. There is no Nx, no Turbo, no Bazel, no Lerna. The Makefile is convenience only.
- A JavaScript project. The optional sim-dashboard is the only place TypeScript is allowed.
- A "we made up the numbers to make the demo look good" project. Datasets must be traceable to public sources.

## 3. Repository Layout

```
project-santara/
  services/
    sim-engine/         # Go performance tier (gRPC server, tick loop)
    sim-gateway/        # Python A2A router, MCP hub, JWT auth
    sim-id-fiskal/      # Indonesia fiscal stress test (Anchor 1)
    sim-id-politik/     # Indonesia political dynamics (Anchor 2)
    sim-id-iklim/       # Indonesia climate emergency (Anchor 3)
    sim-id-agraria/     # Indonesia agrarian micro-economy (Anchor 4)
  libs/
    sim-kernel/         # Shared Python library, the only thing services import
    rpc-contracts/      # Protobuf contracts for the gRPC boundary
  docs/                 # English documentation (canonical)
    AGENTS.md           # This file
    ARCHITECTURE.md     # Canonical architecture
    COMMIT_STYLE.md     # Commit message convention
    ROADMAP.md          # Phased roadmap and decision log
  docs-id/              # Indonesian documentation (mirror)
    PANDUAN.md          # Indonesian front door
    ARCHITECTURE.md     # Indonesian mirror of architecture
    ROADMAP.md          # Indonesian mirror of roadmap
  README.md             # English front door
  RELEASE.md            # Release and packaging strategy
  CONTRIBUTING.md       # Contributor guide
  CODE_OF_CONDUCT.md    # Community standards
  SECURITY.md           # Vulnerability reporting
  CHANGELOG.md          # Release history
  LICENSE               # Apache 2.0
  Makefile              # Convenience targets
```

Each service and library has its own README. Read the README of the service before editing it.

## 4. Architecture in One Page

Two tiers, one shared library.

- Intelligence tier: Python 3.12, FastAPI, Pydantic AI, A2A, MCP, asyncpg.
- Performance tier: Go 1.22+, standard library, zerolog, custom tick engine, gRPC server.
- Shared library: `sim-kernel` (pip-installable, no I/O of its own).
- Inter-Python communication: A2A Protocol (Linux Foundation), JSON-RPC over HTTP.
- Python to Go: gRPC, protobuf contracts in `libs/rpc-contracts/`.
- Tool and data: Model Context Protocol (Linux Foundation) with Streamable HTTP.
- Events: Redis 7 Streams with the outbox pattern for at-least-once delivery.
- Storage: PostgreSQL 16 per service. No cross-service joins.
- Deployment: Docker Compose for local and single-node. K3s for multi-node (v1.5.0).

Full architecture is in [docs/ARCHITECTURE.md](./ARCHITECTURE.md). The architecture document is the source of truth. If this file disagrees with ARCHITECTURE.md, ARCHITECTURE.md wins.

## 5. The Go Service Is Not a Joke

`services/sim-engine` is a first-class performance tier. It is the only service that runs the tick loop. The Python services do reasoning and orchestrate; the Go service does the hot loop. Both are necessary.

Implications:

- The Go service is not a "future rewrite." It is Phase 0 work, parallel to the sim-kernel scaffold.
- The Go service uses gRPC as the wire format. The Python services are gRPC clients.
- The Go service runs in-memory only in v0.1.0. Persistent state for the Go service is a v1.5.0 feature. This is an explicit decision, not a deferred one.
- The Go service is the natural place to use Go's strengths: goroutines, channels, low memory footprint, fast startup. Do not pull in heavy dependencies without a written reason.
- Do not propose replacing the Go service with a Python implementation. Do not propose replacing the Python services with a Go implementation. The hybrid is the architecture.

## 6. Coding Style (Hard Rules)

### Python

- Python 3.12+. Use `match` statements, type parameters, the new `|` union syntax, and `typing.Self` where appropriate.
- Type hints on every public function. Strict mode in `pyproject.toml` for new code.
- `async def` for I/O, `def` for pure functions.
- Pydantic v2 for all data models. Use `model_dump()` and `model_validate()`.
- Black formatting, isort for imports, ruff for lint. Line length 100.
- snake_case functions and variables, PascalCase classes, UPPER_SNAKE constants.
- Google-style docstrings on public functions. Internal functions: optional but encouraged.
- No wildcard imports. No `from x import *`.
- No `as any`, no `# type: ignore`, no `# noqa` without an inline reason comment.

### Go

- gofmt before commit. golangci-lint with the default linter set.
- Standard library first. Every external dependency needs a written reason in the changelog.
- `context.Context` is the first argument to any blocking function.
- Wrap errors with `fmt.Errorf("...: %w", err)`. Return errors. No panics in library code.
- Package names lowercase, no underscores. Unexported names start lowercase. Acronyms all-caps (`URL`, `HTTP`).
- Prefer `slices`, `maps`, and other standard library generics over hand-rolled loops.
- Use `zerolog` for structured logging. Do not use `log` from the standard library.
- `go.mod` declares `github.com/raihanpka/sim-engine` as the module path. Do not change this.

### Markdown

- No emoji. Anywhere. Even in code examples. Even in headings. Even in commit messages.
- No em dash (U+2014) or en dash (U+2013). Use a single hyphen with spaces around it, or rewrite the sentence.
- Mermaid for diagrams. GitHub renders Mermaid natively. Do not ship ASCII art diagrams.
- ATX headers (`#`, `##`, `###`).
- Hyphens for unordered lists, not asterisks.
- Fenced code blocks with language hints.

## 7. Documentation Style

- Bilingual. Every user-facing string and every documentation file lives in both English and Bahasa Indonesia. The English version is canonical.
- Tone: senior project manager or staff engineer. Honest about state. No aspirational metrics. No "we will" without a date.
- Code examples must actually run. If you show a command, the command must work in a fresh clone with the documented prerequisites.
- Citations for non-obvious claims. Link to the source.
- Tables for structured comparisons. Use Markdown tables, not bullet lists of `key: value`.

## 8. Commit and PR Style

See [COMMIT_STYLE.md](./COMMIT_STYLE.md) for the full convention. The short version:

```
type(scope): short description

- Bullet one describing the change.
- Bullet two describing the change.
- Bullet three describing the change.

Fixes #123.
```

- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`.
- Scopes: `sim-kernel`, `sim-engine`, `sim-gateway`, `sim-id-fiskal`, `sim-id-politik`, `sim-id-iklim`, `sim-id-agraria`, `rpc-contracts`, `sim-datasets`, `docs`, `docs-id`, `ci`, `root`.
- Subject: imperative, sentence case, no period, under 72 characters.
- Body: bullets, capitalized, no trailing period, 72-character wrap.
- One logical change per commit. Squash fixups locally before pushing.

Pull requests: open as draft early, run the full test suite, address review comments, squash-merge on approval.

## 9. Don'ts (Hard Blocks)

These are explicit anti-patterns. A pull request that does any of these will be rejected.

- **No emoji in code, comments, documentation, or commit messages.** Not even one.
- **No em dash or en dash.** Use a single hyphen with spaces, or rewrite the sentence.
- **No ASCII art diagrams.** Use Mermaid.
- **No JavaScript framework for the platform itself.** The optional sim-dashboard is the only TypeScript surface. Do not add Next.js, React (outside sim-dashboard), Vue, Svelte, or any other JS framework to the platform.
- **No monorepo build tool in v1.0.** No Nx, no Turbo, no Bazel, no Lerna. The Makefile is convenience only.
- **No DDD tactical patterns in Python.** Aggregates, value objects, domain services in the Go service are fine. Do not introduce the same patterns in Python services; Python uses module-level functions and Pydantic models.
- **No ORM.** Use `asyncpg` with raw SQL and a thin repository helper. No SQLAlchemy, no Tortoise, no Piccolo.
- **No Alembic or other migration tool.** Migrations are plain SQL files. The migration runner is a small script in sim-kernel.
- **No proposal to throw away working code in the name of "simplicity" or "modernization."** The reset that produced v0.0.0 was a one-time event driven by the legacy architecture not matching the new one. Do not propose another one.
- **No emoji in commit messages.** The previous bullet is serious. The previous one is serious too.
- **No "we" in marketing-speak.** Use first-person singular for the maintainer, or third-person for the project. Avoid "we are excited to announce" and similar patterns.
- **No "Trust me bro" claims about datasets.** Every row must trace to a public source. Provenance is mandatory.
- **No generated content that pretends to be data.** AI is allowed as a curator. AI is not allowed as a source.

## 10. How to Run, Test, Lint

```
make install        # Install sim-kernel and Python services (when they have pyproject.toml)
make test           # Run all tests (Python + Go)
make test-py        # Python tests only
make test-go        # Go tests (services/sim-engine, when tests exist)
make test-kernel    # sim-kernel tests only
make lint           # Ruff for Python, golangci-lint for Go
make format         # Black-equivalent for Python, gofmt for Go
make build-go       # Build the Go service binary
make docker-up      # Bring up the planned Docker Compose stack
make docker-down    # Tear down the stack
make clean          # Remove build artifacts and caches
```

The Makefile is intentionally simple. Do not turn it into a build orchestrator. Each service has its own `pyproject.toml` or `go.mod` and can be built independently.

## 11. Bilingual Content

- English is canonical. All design decisions and rationale live in `docs/`.
- Bahasa Indonesia is a first-class mirror. All user-facing content lives in `docs-id/`.
- Code comments and identifiers: English. Exception: domain-specific strings in locale data files.
- User-facing strings: both languages. Store them in `libs/sim-kernel/src/sim_kernel/locales/`.
- Commit messages: English. Indonesian is fine in the body if the change is Indonesian-specific, but the subject must be in English.
- Issue and PR templates: bilingual. English first, Indonesian second.

When you write or update a doc, you update both copies. If the Indonesian copy cannot keep up, the English version is the source of truth and the Indonesian copy is marked "needs translation."

## 12. When You Are Unsure

- Read [docs/ARCHITECTURE.md](./ARCHITECTURE.md). The architecture is the source of truth.
- Read [docs/ROADMAP.md](./ROADMAP.md). The roadmap tells you what is done, what is in progress, and what is aspirational.
- Read the README of the service or library you are about to edit.
- Search the existing code for similar patterns. Match them.
- When the existing code has no similar pattern, the new pattern must be minimal. No new abstraction for a one-time operation.
- When the design feels wrong, raise a concern before writing code. State the observation, propose an alternative, ask for confirmation.
- When you are asked to do something that violates the don'ts above, refuse politely and explain which rule is at stake.
- When you are not sure whether something is a hard block or a soft guideline, treat it as a hard block until a human clarifies.

Welcome to Project Santara. Build real things. Be honest about what is real.
