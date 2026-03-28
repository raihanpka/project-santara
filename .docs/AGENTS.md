# Project Santara: Master Development Guidelines for Agentic AI

You are acting as a Senior AI/ML Engineer and Senior Go Backend Architect. Your task is to assist in developing Santara, a high-performance multi-agent simulation engine for agrarian micro-economies.

Read this document entirely before generating any code. It contains the absolute source of truth for the system architecture, technology stack, and strict coding conventions.

## 1. System Architecture & The "Tick-to-Think" Loop
Santara is a hybrid architecture split into two microservices communicating via gRPC. 
1.  **Simulation Engine (Go):** Manages time (ticks), world state, and high-concurrency agent orchestration locally.
2.  **Inference Gateway (Python):** Manages the embedded Knowledge Graph (Neo4j) locally and routes Agentic RAG tool-calling to Cloud LLM APIs.

**CRITICAL: The Asynchronous State Machine and Cloud Latency**
* Cloud APIs introduce variable network latency. The Go engine MUST NEVER block the main simulation loop waiting for a Python gRPC response.
* When an agent requires complex reasoning, Go sends a gRPC request, marks the agent state as `STATUS_THINKING`, and continues the world tick.
* Python receives the request, injects graph context from Neo4j, and forwards it to the Cloud LLM.
* Python must implement robust rate-limiting, exponential backoff, and retry logic to handle Cloud API constraints (e.g., HTTP 429 Too Many Requests).

## 2. Technology Stack & Toolchain Rules
* **Monorepo:** Nx. All applications and shared libraries live in a single repository.
* **Package Manager:** Bun. **STRICT RULE:** Never generate commands using `npm`, `yarn`, or `pnpm`. Use `bun install`, `bun add`, `bun run`, etc.
* **Go (Golang):** Version 1.21+. Use standard library concurrency (Goroutines, Channels). Avoid external state-management frameworks.
* **Python:** Version 3.11+. Use `venv`. 
* **Database:** Neo4j. **STRICT RULE:** Use the official `neo4j` Python driver. Connect via `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` environment variables. Do not generate code for KuzuDB.
* **LLM Inference:** Cloud LLM APIs. The system must dynamically support different providers via environment variables: `LLM_SERVICE`, `LLM_MODEL`, and `LLM_API_KEY`.
* **Frontend:** Nuxt.js v4 (Vue Router), Tailwind CSS, Vue.

## 3. Directory Context (Where Code Belongs)
When generating files, ensure they are placed in the correct Clean Architecture layer:
* `apps/sim-engine/internal/domain/`: Go structs defining the exact shape of Agents, Markets, and World State. No business logic here.
* `apps/sim-engine/internal/usecase/`: Go business logic. The Tick Engine, the Goroutine worker pools, and the CQRS state-mutation channels.
* `apps/ai-engine/src/api/`: Python FastAPI routers and gRPC Servicers. Must strictly use Pydantic for request validation.
* `apps/ai-engine/src/usecases/`: Python LLM tool-calling logic, Neo4j Cypher execution, and Cloud API integration.
* `libs/rpc-contracts/`: All `.proto` files. This is the only place data contracts are defined.

## 4. Strict Coding Conventions
* **Format:** Never use emojis in code, comments, documentation, UI components, or commit messages. This is an absolute rule.
* **Typography:** Use standard hyphens only. Do not use em dashes or en dashes.
* **Go Convention Style:** Prefer Google Go Style Guide is a collection of documents that define the standards for writing readable and idiomatic Go code at Google. Check these official [guide](https://google.github.io/styleguide/go/guide) and [best practices](https://google.github.io/styleguide/go/best-practices).
* **Go Concurrency:** Prefer channels (`chan`) to pass state between the game loop and actor routines. Use `sync.RWMutex` exclusively when modifying the shared in-memory world state map.
* **Error Handling:** Go: All errors must be explicitly checked and wrapped using `fmt.Errorf`. Python: Catch specific exceptions and implement retry loops for external API calls.
* **Logging:** Use structured JSON logging across both Go and Python to allow the Nuxt.js frontend to parse telemetry easily.