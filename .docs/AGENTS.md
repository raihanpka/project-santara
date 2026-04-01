# Project Santara: Development Guidelines and Rules for Agentic AI

You are acting as a Senior AI/ML Engineer and Senior Go Backend Architect. Your task is to assist in developing Santara, a high-performance multi-agent simulation engine for agrarian micro-economies.

Read this document entirely before generating any code. This document serves as the absolute source of truth for Project Santara's architecture, following Domain-Driven Design (DDD) and Clean Architecture principles optimized for both Go and Python.

## 0. Core Architectural References & Style Guides
All code generated MUST adhere to the patterns and styles defined in these authoritative sources:

### A. Go (Simulation Engine)
*   **ThreeDotsLabs: Repository Pattern in Go:** [threedots.tech/post/repository-pattern-in-go/](https://threedots.tech/post/repository-pattern-in-go/)
*   **ThreeDotsLabs: Introducing Clean Architecture:** [threedots.tech/post/introducing-clean-architecture/](https://threedots.tech/post/introducing-clean-architecture/)
*   **ThreeDotsLabs: Wild Workouts (Example Implementation):** [github.com/ThreeDotsLabs/wild-workouts-go-ddd-example](https://github.com/ThreeDotsLabs/wild-workouts-go-ddd-example)
*   **Google Go Style Guide:** [google.github.io/styleguide/go/](https://google.github.io/styleguide/go/)

### B. Python (Inference Gateway)
*   **ThreeDotsLabs: Introducing Clean Architecture:** [threedots.tech/post/introducing-clean-architecture/](https://threedots.tech/post/introducing-clean-architecture/)
*   **Pydantic V2 Documentation:** [docs.pydantic.dev](https://docs.pydantic.dev)

## 1. System Architecture & The "Tick-to-Think" Loop
Santara is a hybrid, distributed simulation engine split into two microservices communicating via gRPC. 
1.  **Simulation Engine (Go):** High-concurrency agent orchestration utilizing a Clean Architecture + DDD approach.
2.  **Inference Gateway (Python):** Manages the Graph Knowledge Base (Neo4j) and Cloud Inference routing.

**CRITICAL: The Asynchronous State Machine and Cloud Latency**
* Cloud APIs introduce variable network latency. The Go engine MUST NEVER block the main simulation loop waiting for a Python gRPC response.
* When an agent requires complex reasoning, Go sends a gRPC request, marks the agent state as `STATUS_THINKING`, and continues the world tick.
* Python receives the request, injects graph context from Neo4j, and forwards it to the Cloud LLM.
* Python must implement robust rate-limiting, exponential backoff, and retry logic to handle Cloud API constraints (e.g., HTTP 429 Too Many Requests).

## 2. Technology Stack & Framework Selection

### A. Simulation Engine (Go)
*   **Concurrency:** Standard Go Concurrency (Goroutines, Channels).
*   **Communication:** `google.golang.org/grpc` and `google.golang.org/protobuf`.
*   **Logging:** `github.com/rs/zerolog` for structured JSON logging.
*   **Testing & Mocking:** `testing` (stdlib), `github.com/stretchr/testify`, and `github.com/vektra/mockery/v2`.
*   **Environment:** `github.com/caarlos0/env/v11` for type-safe config.

### B. Inference Gateway (Python)
*   **API Framework:** `FastAPI` (Asynchronous).
*   **Schema/Validation:** `Pydantic V2`.
*   **Graph DB:** Official `neo4j` Python driver.
*   **Inference Clients:** `google-generativeai`, `anthropic`, `openai`.
*   **Environment Management:** `python-dotenv`.
*   **Testing:** `pytest` and `httpx` (for async testing).

### C. Toolchain & Monorepo
* **Orchestration:** `Nx` (Bun-integrated).
* **Package Manager:** `Bun` (Strict rule: No npm/yarn).
* **Frontend:** `Nuxt.js v4` (Vue) + `Tailwind CSS`.

## 3. Go Architecture & DDD Patterns (simulation-engine)
Santara strictly follows the ThreeDotsLabs Go Best Practices (DDD + Clean Architecture):

### A. Layered Directory Structure
* `internal/domain/`: Pure domain entities and business logic. This layer MUST NOT depend on any other layers (Domain Isolation). If an entity needs to persist itself, it defines a repository interface here.
* `internal/app/`: Application layer coordinating use cases. Split into `commands` (write-heavy logic) and `queries` (read-heavy logic) for a CQRS-Lite approach.
* `internal/adapters/`: Implementation details (Infrastructure). Concrete repository implementations (e.g., Neo4j, Redis, in-memory) and gRPC clients live here.
* `internal/ports/`: Entry points to the app. gRPC servers, REST handlers, and CLI commands. They only talk to the `app` layer.

### B. Repository Pattern Rules
* **Small Interfaces:** Define interfaces where they are *used* (consumer-owned). Domain repos live in `domain`, Application repos live in `app`.
* **Domain Entities only:** Repository interfaces MUST use Domain entities, never database models or gRPC types.
* **Decoupled Persistence:** The simulation engine defaults to in-memory state. Adapters for persistent storage should be swappable.

### C. CQRS-Lite Strategy
* Use a central `Application` struct (in `internal/app/app.go`) to expose all available commands and queries.
* Each Command/Query is a separate struct with a `Handler`. This reduces code bloat in a single "Service" file.

## 4. Structural Definitions (Service Layouts)

### A. Simulation Engine (`apps/sim-engine/`)
Following ThreeDotsLabs Clean Architecture:
*   `cmd/sim-engine/main.go`: Application entrypoint/dependency injection root.
*   `internal/domain/`: Pure entities (Agent, Market). Defines repository interfaces.
*   `internal/app/`: Use-case layer.
    *   `internal/app/commands/`: Command handlers for state mutation (e.g., `ProcessTick`).
    *   `internal/app/queries/`: Query handlers for reading state (e.g., `GetWorldSnapshot`).
*   `internal/adapters/`: Concrete implementations of domain/app repositories (e.g., `Neo4jRepository`, `InMemoryState`).
*   `internal/ports/`: Communication entrypoints (gRPC servers, CLI).

### B. Inference Gateway (`apps/ai-engine/`)
Following Python Clean Architecture (Adapters/Port approach):
*   `src/api/`: FastAPI routers and gRPC Servicers (Ports).
*   `src/domain/`: Data models (Pydantic) and pure logic.
*   `src/usecases/`: Application logic orchestration (Services).
*   `src/infrastructure/`: Repositories (Neo4j clients) and LLM clients (Adapters).

### C. Contracts & Shared (`libs/`)
*   `libs/rpc-contracts/`: Source `.proto` files for cross-service communication.

## 5. Strict Coding Conventions
* **Error Handling:** Use an "Error Slug" or standard error constants in the Domain (e.g., `ErrAgentHungry`). Wrap external errors but don't leak infrastructure details at the Domain level.
* **Format:** Never use emojis.
* **Typography:** Standard hyphens only.
* **Go Concurrency:** Use the Tick-to-Think loop. Channels for communication, `sync.RWMutex` for safe state modification in the "Tick" thread.
* **Testability & Mocking:** All external dependencies (Repositories, gRPC Clients) MUST use interfaces defined by the consumer-layer. Use `mockery` or handwritten mocks for unit testing the `app` layer in isolation from the `adapters`.
* **Logging:** Use structured JSON logging across both Go and Python to allow the Nuxt.js frontend to parse telemetry easily.