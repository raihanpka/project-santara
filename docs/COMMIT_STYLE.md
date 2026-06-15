# Commit Style

This document defines the commit message convention for Project Santara. The convention is derived from the existing git history and from the Conventional Commits specification.

## Format

Every commit message has two parts: a single-line subject and an optional multi-line body.

### Subject Line

```
<type>(<scope>): <description>
```

- **Type** is one of: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`.
- **Scope** is in parentheses. It names the project area affected.
- **Description** is a short imperative sentence in sentence case. No period at the end. No more than 72 characters total.

### Body

```
- Bullet one describing the change.
- Bullet two describing the change.
- Bullet three describing the change.
```

- Each bullet starts with a capital letter and ends without a period.
- Each bullet describes one logical change.
- Use the imperative mood ("Add", "Fix", "Update", "Remove", not "Added", "Fixed", "Updated", "Removed").
- Wrap body lines at 72 characters.
- Reference issues with `Fixes #123` or `Refs #456` on the last line if applicable.

### Breaking Changes

A breaking change is indicated by either:

- A `!` after the type/scope: `feat(api)!: remove legacy /v1/users endpoint`
- A `BREAKING CHANGE:` footer in the body: `BREAKING CHANGE: removed /v1/users endpoint, use /v2/users`

Either form is acceptable. Pick one per commit, not both.

## Types

| Type | Purpose |
|---|---|
| feat | A new feature or capability |
| fix | A bug fix |
| docs | Documentation only change |
| style | Formatting, missing semicolons, etc. (no code change) |
| refactor | Code change that neither fixes a bug nor adds a feature |
| test | Adding or fixing tests |
| chore | Build, dependency, tooling, or non-source change |
| build | Build system or external dependency change |
| ci | CI configuration change |
| perf | Performance improvement |

## Scopes

Scopes name the project area affected. The canonical scopes are:

| Scope | Area |
|---|---|
| sim-kernel | the shared Python library |
| sim-gateway | the Python gateway service |
| sim-id-fiskal | the Indonesia fiscal service |
| sim-id-politik | the Indonesia political service |
| sim-id-iklim | the Indonesia climate service |
| sim-id-agraria | the Indonesia agrarian service |
| sim-engine | the Go performance tier |
| rpc-contracts | the shared protobuf contracts |
| sim-datasets | the curated Hugging Face datasets |
| docs | the docs/ directory |
| docs-id | the docs-id/ directory |
| ci | GitHub Actions, Docker Compose, or other CI |
| root | the root files (Makefile, .gitignore, RELEASE.md, etc.) |

If a commit affects multiple scopes, pick the dominant one. If there is no dominant scope, omit the scope: `chore: bump ruff version`.

## Examples from History

The existing commit log shows the style in use:

```
feat(internalization): enhance localization for agent decision-making and simulation evaluation

- Refactor system prompt in AgenticRAG to be locale-aware, allowing for dynamic adaptation based on country context.
- Introduce SimulationEvaluator for comprehensive evaluation of simulation logs using LLM-as-a-Judge pattern.
- Implement detailed evaluation models including EvaluationCategory, EvaluationScore, and SimulationEvaluation.
- Add integration tests for the AI Engine, covering end-to-end flow from agent state to decision-making.
- Create mock implementations for Neo4j client and LLM router to facilitate testing without external dependencies.
- Enhance currency formatting and localization features across various components.
```

```
feat(ai-engine): implement graph pruning engine and initialize multi-service project structure for AI and simulation engines
```

```
docs(guide): add some reference to clean architecture from ThreeDotsLabs
```

```
chore(init): setup base project structure, development plan, and guidelines
```

The pattern is clear. The body is for detail. The subject is for scanning.

## Validation

Commit messages are validated by commitlint. The configuration is in `.commitlintrc.json` at the repository root. A commit that does not match the format will fail CI.

## Reverts

A revert commit uses the `revert` type:

```
revert: feat(sim-id-fiskal): add pertamax shock scenario

This reverts commit 1234abc.
```

## Merge Commits

Pull requests are squash-merged. The squash commit subject should match the pull request title, which should follow this convention. The body of the squash commit is the pull request description.

## Why This Style

The subject-first format makes `git log --oneline` scannable. The type prefix makes it easy to filter (`git log --grep=^feat`). The scope makes it obvious which area of the codebase is affected. The body documents the actual change for future readers.

This style matches the convention used by Angular, Vue, Nuxt, and many other open-source projects. The existing Project Santara history already uses this style. We are documenting the convention, not inventing a new one.
