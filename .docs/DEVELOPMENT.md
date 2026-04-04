# Project Santara: Technical Roadmap and SDLC

This document defines the strict, phase-by-phase development lifecycle for the Santara monorepo. All development must adhere to the patterns and references defined below.

## 0. Technical References & Authority
Refer to these documents for architectural decisions and code style:

### A. Go (Simulation Engine)
*   **ThreeDotsLabs: Repository Pattern in Go:** [threedots.tech/post/repository-pattern-in-go/](https://threedots.tech/post/repository-pattern-in-go/)
*   **ThreeDotsLabs: Introducing Clean Architecture:** [threedots.tech/post/introducing-clean-architecture/](https://threedots.tech/post/introducing-clean-architecture/)
*   **ThreeDotsLabs: Wild Workouts (Example Implementation):** [github.com/ThreeDotsLabs/wild-workouts-go-ddd-example](https://github.com/ThreeDotsLabs/wild-workouts-go-ddd-example)
*   **Google Go Style Guide:** [google.github.io/styleguide/go/](https://google.github.io/styleguide/go/)

### B. Python (Inference Gateway)
*   **ThreeDotsLabs: Introducing Clean Architecture:** [threedots.tech/post/introducing-clean-architecture/](https://threedots.tech/post/introducing-clean-architecture/)
*   **Pydantic V2 Documentation:** [docs.pydantic.dev](https://docs.pydantic.dev)
*   **Neo4j Python Driver:** [neo4j.com/docs/python-manual/current/](https://neo4j.com/docs/python-manual/current/)

## 1. Environment Variables Configuration
The Python AI engine requires a `.env` file at its root to manage Cloud LLM routing and the Neo4j connection:
* `LLM_SERVICE`: The provider to use (e.g., `gemini`, `anthropic`, `openai`).
* `LLM_MODEL`: The specific model string (e.g., `gemini-3.1-flash`, `claude-sonnet-4.5`, `gpt-4o-mini`).
* `LLM_API_KEY`: The authentication token.
* `NEO4J_URI`: The Bolt connection URI (e.g., `bolt://localhost:7687`).
* `NEO4J_USER`: The database username (e.g., `neo4j`).
* `NEO4J_PASSWORD`: The database password.

## Phase 1: Knowledge Graph and Cloud Inference Gateway
**Goal:** Establish the Python AI Engine, the Neo4j knowledge graph, and the rate-limited Cloud LLM router.

* [x] Initialize the Nx workspace with Bun. Scaffold the `ai-engine` Python app.
* [x] **Neo4j Initialization:** Write Python scripts in `src/infrastructure/` to connect to Neo4j and apply schema constraints. Define the schema (Nodes: `Farmer`, `Market`, `Region`. Edges: `Connected_To`, `Trades_With`).
* [x] **Data Ingestion:** Write the parser to ingest raw OpenStreetMap and CSV data into Neo4j.
* [x] **Eager Graph Pruning:** Implement community detection to summarize Neo4j neighborhoods during ingestion, keeping LLM prompts small to optimize cloud token costs.
* [x] **Cloud LLM Client:** Implement the integration layer in `src/infrastructure/llm_client.py` that reads the `LLM_SERVICE` variables and executes prompts with robust exponential backoff and concurrency limits.

## Phase 2: Contracts and Simulation Engine (Go DDD Setup)
**Goal:** Define the data boundaries and build the Go high-concurrency tick loop using a Clean Architecture approach.

* [x] **Protobuf Definition:** Create `libs/rpc-contracts/simulation.proto`. Define messages for `AgentState`, `WorldState`, and `ActionDecision`.
* [x] **Stub Generation:** Configure the `Makefile` to compile the `.proto` files into Go and Python stubs.
* [x] **Go DDD Scaffold:** Initialize `apps/sim-engine/internal/` with `domain`, `app`, `adapters`, and `ports`.
* [x] **Domain Entities:** Define the `Agent` and `Market` entities in `internal/domain/`. Implement pure business logic (e.g., `agent.Eat()`, `agent.Move()`).
* [x] **CQRS Implementation:** Implement `ProcessTick` as a Command struct in `internal/app/commands/` and `GetWorldState` as a Query in `internal/app/queries/`.
* [x] **Worker Pool:** Implement the Goroutine worker pool that executes agent behavioral loops autonomously.
* [x] **Dependency Injection:** Setup `internal/app/app.go` to provide the command/query handlers to the `ports` layer.
* [x] **In-Memory Repository:** Create an in-memory repository implementation in `internal/adapters/state/` for high-speed simulation access.

## Phase 3: Agentic RAG and Tool Execution
**Goal:** Connect the two systems so agents can reason and act within the simulation.

* [x] **Python Tooling:** Define the exact Python functions the Cloud LLM can call (e.g., `get_local_price(item_id)`, `check_inventory(agent_id)`).
* [x] **LLM Router:** Configure the cloud provider's native tool-calling API to force the LLM to output decisions in strict JSON formats matching the Protobuf contracts.
* [x] **Integration Test:** Run a 10-tick simulation headless. Verify that Go sends requests, Python queries Neo4j, the Cloud LLM returns a decision, and Go updates the state without deadlocking.

## Phase 4: Frontend Visualization and Evaluation
**Goal:** Build the interactive dashboard and the deterministic QA system.

* [ ] Scaffold the `frontend` Nuxt.js app using Nx.
* [ ] **WebSocket Telemetry:** Implement a WebSocket server in Go to broadcast batched state updates every 10 ticks.
* [ ] **UI Components:** Build the React components to parse the WebSocket JSON and render the simulation state.
* [ ] **LLM-as-a-Judge:** Write the final Python script (`src/usecases/evaluate.py`) that sends the simulation logs to the Cloud LLM to generate the Post-Mortem Report.