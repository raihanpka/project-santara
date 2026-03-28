# Project Santara: Technical Roadmap and SDLC

This document defines the strict, phase-by-phase development lifecycle for the Santara monorepo. Agents must verify prerequisites are met before moving to the next phase.

## Environment Variables Configuration
The Python AI engine requires a `.env` file at its root to manage Cloud LLM routing and the Neo4j connection:
* `LLM_SERVICE`: The provider to use (e.g., `gemini`, `anthropic`, `openai`).
* `LLM_MODEL`: The specific model string (e.g., `gemini-3.1-flash`, `claude-sonnet-4.5`, `gpt-4o-mini`).
* `LLM_API_KEY`: The authentication token.
* `NEO4J_URI`: The Bolt connection URI (e.g., `bolt://localhost:7687`).
* `NEO4J_USER`: The database username (e.g., `neo4j`).
* `NEO4J_PASSWORD`: The database password.

## Phase 1: Knowledge Graph and Cloud Inference Gateway
**Goal:** Establish the Python AI Engine, the Neo4j knowledge graph, and the rate-limited Cloud LLM router.

* [ ] Initialize the Nx workspace with Bun. Scaffold the `ai-engine` Python app.
* [ ] **Neo4j Initialization:** Write Python scripts in `src/infrastructure/` to connect to Neo4j and apply schema constraints. Define the schema (Nodes: `Farmer`, `Market`, `Region`. Edges: `Connected_To`, `Trades_With`).
* [ ] **Data Ingestion:** Write the parser to ingest raw OpenStreetMap and CSV data into Neo4j.
* [ ] **Eager Graph Pruning:** Implement community detection to summarize Neo4j neighborhoods during ingestion, keeping LLM prompts small to optimize cloud token costs.
* [ ] **Cloud LLM Client:** Implement the integration layer in `src/infrastructure/llm_client.py` that reads the `LLM_SERVICE` variables and executes prompts with robust exponential backoff and concurrency limits.

## Phase 2: Contracts and Simulation Engine
**Goal:** Define the data boundaries and build the Go high-concurrency tick loop.

* [ ] **Protobuf Definition:** Create `libs/rpc-contracts/simulation.proto`. Define messages for `AgentState`, `WorldState`, and `ActionDecision`.
* [ ] **Stub Generation:** Configure the `Makefile` to compile the `.proto` files into Go and Python stubs.
* [ ] Scaffold the `sim-engine` Go app.
* [ ] **Tick Loop:** Implement the master time-loop in `internal/usecase/tick_engine.go`.
* [ ] **Agent Goroutines:** Implement the worker pool where each Goroutine represents an active agent.
* [ ] **gRPC Client:** Implement the Go client that sends `AgentState` to Python and handles the asynchronous callback.

## Phase 3: Agentic RAG and Tool Execution
**Goal:** Connect the two systems so agents can reason and act within the simulation.

* [ ] **Python Tooling:** Define the exact Python functions the Cloud LLM can call (e.g., `get_local_price(item_id)`, `check_inventory(agent_id)`).
* [ ] **LLM Router:** Configure the cloud provider's native tool-calling API to force the LLM to output decisions in strict JSON formats matching the Protobuf contracts.
* [ ] **Integration Test:** Run a 10-tick simulation headless. Verify that Go sends requests, Python queries Neo4j, the Cloud LLM returns a decision, and Go updates the state without deadlocking.

## Phase 4: Frontend Visualization and Evaluation
**Goal:** Build the interactive dashboard and the deterministic QA system.

* [ ] Scaffold the `frontend` Nuxt.js app using Nx.
* [ ] **WebSocket Telemetry:** Implement a WebSocket server in Go to broadcast batched state updates every 10 ticks.
* [ ] **UI Components:** Build the React components to parse the WebSocket JSON and render the simulation state.
* [ ] **LLM-as-a-Judge:** Write the final Python script (`src/usecases/evaluate.py`) that sends the simulation logs to the Cloud LLM to generate the Post-Mortem Report.