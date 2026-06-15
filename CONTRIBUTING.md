# Contributing to Project Santara

Thank you for your interest in contributing. This guide explains how to participate, what we expect from contributors, and how the contribution process works. Reading this document fully before opening a pull request will save time for everyone.

For the commit message convention, see [COMMIT_STYLE.md](docs/COMMIT_STYLE.md). For the release and distribution strategy, see [RELEASE.md](./RELEASE.md).

## Table of Contents

1. Code of Conduct
2. How to Contribute
3. Development Setup
4. Coding Standards
5. Testing
6. Pull Request Process
7. Issue Guidelines
8. AI-Assisted Contributions
9. Translations and Localization
10. Release Process
11. Recognition

## 1. Code of Conduct

All participants are expected to follow the [Code of Conduct](./CODE_OF_CONDUCT.md). The short version: be respectful, assume good faith, give credit, focus on what is best for the community. Violations can be reported to conduct@projectsantara.id.

## 2. How to Contribute

You can contribute in many ways.

- **Code.** Pick an issue labeled `good first issue` or `help wanted`, or open a proposal first.
- **Documentation.** Fix typos, clarify language, add examples, translate to Bahasa Indonesia.
- **Scenarios.** Ship a new runnable scenario that answers a real question (see ARCHITECTURE.md section 6 for the canonical flow).
- **Bug reports.** Use the bug report template. Include reproduction steps.
- **Feature proposals.** Open an issue with the `proposal` label. Wait for feedback before writing code.
- **Reviews.** Review open pull requests. Every maintainer comment is a learning opportunity.
- **Translations.** Help translate prompts, docs, and scenarios to other languages. Bahasa Indonesia is the priority non-English language.
- **Protobuf contracts.** Edit `libs/rpc-contracts/proto/simulation.proto` when the wire format needs to change. Run the regen script and verify both sides.

## 3. Development Setup

### Prerequisites

- Python 3.12 or newer
- Go 1.22 or newer
- Docker and Docker Compose
- Git
- 4 GB of free RAM
- 10 GB of free disk space

### First-time setup

```
git clone https://github.com/raihanpka/project-santara
cd project-santara
cp .env.example .env
make install
make test
```

The `make install` target installs sim-kernel and any Python service that has a `pyproject.toml`. The `make test` target runs the Python and Go test suites.

### Running individual services

Each service lives under `services/<name>/`. To run a service outside Docker during development:

```
cd services/sim-id-fiskal
pip install -e ".[dev]"
uvicorn src.sim_id_fiskal.main:app --reload --port 8001
```

Hot reload is enabled. The service will pick up code changes without restart.

```
cd services/sim-engine
go test ./...
go build -o bin/sim-engine ./cmd/server
```

## 4. Coding Standards

### Python

- **Style.** Black formatter, isort for imports, ruff for lint. Configuration in `pyproject.toml`.
- **Typing.** Type hints on every public function. Strict mode where possible.
- **Async.** Use `async def` for any function that performs I/O. Use `def` for pure functions.
- **Pydantic.** Use Pydantic v2 for all data models. Use `model_dump()` and `model_validate()` for serialization.
- **Naming.** snake_case for functions and variables, PascalCase for classes, UPPER_SNAKE for constants.
- **Docstrings.** Google style. Required for public functions, optional for internal ones.
- **Line length.** 100 characters. Black will enforce this.

### Go

- **Style.** gofmt, golangci-lint with default linter set.
- **Standard library first.** External dependencies need a written reason in the changelog.
- **Context.** First argument to any blocking function.
- **Errors.** Wrap with `fmt.Errorf("...: %w", err)`. Return errors. No panics in library code.
- **Naming.** Package names lowercase, no underscores. Unexported names start lowercase. Acronyms all-caps (`URL`, `HTTP`).

### Markdown

- **No emoji.** Anywhere. Even in code examples. Even in headings.
- **No em dash or en dash.** Use a single hyphen with spaces around it, or rewrite the sentence.
- **Mermaid for diagrams.** GitHub renders Mermaid natively. Do not ship ASCII art.
- **Headers.** Use ATX style (`#`, `##`, `###`).
- **Lists.** Use hyphens, not asterisks.
- **Code blocks.** Use fenced blocks with language hints.

### Commit messages

See [docs/COMMIT_STYLE.md](./docs/COMMIT_STYLE.md) for the full convention. Quick reference:

```
type(scope): short description

Long description if needed. Wrap at 72.
Fixes #123.
```

Commitlint validates the format. A commit that does not match the format fails CI.

### Branch naming

`type/short-description` in kebab-case. Examples: `feat/pertamax-scenario`, `fix/a2a-timeout`, `docs/panduan-update`.

## 5. Testing

Three layers of tests, all required.

- **Unit tests** for pure functions. Run with `pytest tests/unit/`. Coverage target 80 percent for sim-kernel, 70 percent for services.
- **Integration tests** for service boundaries. Use httpx against a local Docker Compose stack. Run with `pytest tests/integration/`.
- **Scenario tests** that ship with each service. Each scenario is a runnable Python file that proves the service answers a real question. Run with `pytest tests/scenarios/`.

Tests must be reproducible by anyone with the repository. No external API calls in tests. Use fixtures, not live data.

When you fix a bug, write a regression test first. The test fails on the unfixed code and passes on the fixed code.

## 6. Pull Request Process

1. **Fork and branch.** Branch from `main`. Use a feature branch named `type/short-description`.
2. **Make focused commits.** One logical change per commit. Squash fixup commits locally before pushing.
3. **Write tests.** No new code lands without tests. See Testing above.
4. **Update documentation.** If you change behavior, update README, PANDUAN, ARCHITECTURE, ROADMAP, or the relevant ADR.
5. **Update CHANGELOG.** Add an entry under the Unreleased section. Use the same format as existing entries.
6. **Run the full test suite locally.** `make test` must pass before you request review.
7. **Open a draft pull request early.** Mark it as draft. Maintainers will give architectural feedback before you finish.
8. **Mark ready for review.** Remove the draft status. Request review from at least one maintainer.
9. **Address feedback.** Use review comments to improve, but you are not required to accept every suggestion. Explain your reasoning if you disagree.
10. **Squash and merge.** The maintainer will squash and merge once approved. Your commits will appear in `main` as a single commit.

A pull request that does not pass CI will not be merged. A pull request without tests will not be merged. A pull request that changes behavior without documentation will be asked to add documentation.

## 7. Issue Guidelines

### Bug reports

Use the bug report template. Include the following.

- Summary in one sentence
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (Python version, OS, Docker version)
- Relevant logs and screenshots
- Proposed fix if you have one

### Feature proposals

Use the `proposal` label. The proposal should answer the following questions.

- What user problem does this solve?
- Who is affected and how many?
- What is the proposed solution?
- What are the alternatives considered?
- How will we measure success?

Proposals without these five questions will be closed. This is not gatekeeping. It is to save your time and the maintainers' time.

### Questions and discussions

Use GitHub Discussions for questions. Use Issues only for actionable items.

## 8. AI-Assisted Contributions

AI coding assistants are welcome and encouraged. To make the experience smooth for everyone, follow these rules.

- **Read AGENTS.md first.** It contains the project context, code style, and don'ts.
- **Be transparent.** If your pull request was substantially generated by an AI assistant, say so in the description. Reviewers will look more carefully at AI-assisted code, which is fair.
- **You own the code.** A maintainer can ask "why does this line do X" and you need to be able to answer. If you cannot, the code is not ready.
- **No AI-generated issues.** Do not open issues written entirely by an AI without your own review and addition.
- **Respect AGENTS.md do-nots.** Especially: no emoji, no em or en dash, no JavaScript frameworks, no DDD tactical patterns, no proposal to throw away working code.

## 9. Translations and Localization

Bahasa Indonesia is the priority non-English language. To translate or improve a translation, open a pull request against the relevant file. The translation lives in `docs-id/PANDUAN.md` (for the main README) and in the locale files under `libs/sim-kernel/src/sim_kernel/locales/`.

If you want to add a new locale, open a proposal first. The locale system is designed to be extended, but we want to coordinate so that no two contributors add overlapping locales.

## 10. Release Process

See [RELEASE.md](./RELEASE.md) for the full release and distribution strategy. The short version.

- Releases follow Semantic Versioning. Major version bumps require a written rationale in CHANGELOG.
- Pushing a tag of the form `vX.Y.Z` triggers the release pipeline.
- sim-kernel publishes to PyPI via trusted publishing.
- Docker images publish to GitHub Container Registry.
- Curated datasets publish to Hugging Face Hub.
- The Go static binary is attached to the GitHub release.

## 11. Recognition

Every contributor is listed in the AUTHORS file. Significant contributors are listed in CREDITS with their area of contribution. The most active contributors are invited to become maintainers.
