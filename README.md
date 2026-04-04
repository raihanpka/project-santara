# Project Santara: Multi-Agent GraphRAG Simulation for Agrarian Micro-Economies

Project Santara is a blazing fast simulation engine. It leverages Large Language Models (LLMs) and embedded Knowledge Graphs to model supply chain dynamics, food sovereignty, and economic resilience. By utilizing state-of-the-art Agentic RAG and Cross-Agent KV Cache Sharing, the system runs massive multi-agent simulations efficiently, replacing rigid mathematical forecasting with emergent, behavioral modeling.

## Scientific Foundation & Research Validation

The architecture of this project is grounded in recent breakthroughs in Multi-Agent Systems (MAS) and Graph Retrieval-Augmented Generation (GraphRAG). Research confirms that combining structural graph data with LLM reasoning drastically reduces hallucination and enables complex, multi-hop economic simulations.

* **Hybrid Multi-Agent GraphRAG for Complex Systems:** Recent studies validate that modular agent pipelines combining symbolic graph traversal with dense vector retrieval outperform standard RAG in highly structured environments (Papageorgiou et al., 2025).
* **LLM-Driven Supply Chain Consensus:** Literature on InvAgent proves that LLM agents can effectively balance material, processing, and inventory costs, autonomously finding consensus to reduce the bullwhip effect in supply chains (Yinzhu Quan and Zefang Liu, 2025).
* **Agricultural Knowledge Graph Construction:** Frameworks like FARM validate the use of multi-agent workflows to automate the construction of agricultural knowledge graphs, proving that complex environmental and economic dependencies can be mapped efficiently for AI reasoning (Papageorgiou et al., 2025).

## How It Works

Santara utilizes a hybrid architecture to maximize both speed and cognitive capabilities. The data and simulation engines run locally, while complex reasoning can be processed locally or securely routed to state-of-the-art cloud LLMs based on hardware constraints. The simulation operates in four primary steps:

1. **Local Initialization:** The user uploads regional OpenStreetMap files and agricultural CSV data. Santara instantly parses this data into an embedded Neo4j knowledge graph.
2. **Scenario Configuration:** The user defines the agent swarm and injects shock variables, such as a sudden 25% spike in fertilizer costs or a localized flood. 
3. **Execution Phase:** The simulation runs dynamically while the user watches a live, interactive visualization on the Nuxt.js dashboard. The Go concurrency engine ticks through simulated days as agents query market prices via the local graph and route complex negotiation and survival logic to the configured LLM.
4. **Post-Mortem Analysis:** The simulation halts and generates a deterministic Post-Mortem Report using an LLM-as-a-Judge framework. This report highlights exact economic failure points and monopolies, allowing users to propose real-world interventions before crises occur.

---

## Project Structure

```
project-santara/
├── apps/
│   ├── ai-engine/        # Python: Inference Gateway (FastAPI + gRPC)
│   ├── sim-engine/       # Go: Simulation Engine (High-concurrency tick loop)
│   └── frontend/         # Nuxt.js: Real-time Dashboard
├── libs/
│   └── rpc-contracts/    # Protobuf gRPC contracts
├── infra/
│   └── docker/           # Docker configurations
├── Makefile               # Development commands
└── .docs/                # Architecture documentation
```

## Technologies Stack

This project utilizes open-source frameworks and libraries to ensure flexible deployment and high performance.

* **Simulation Engine:** Go (Golang) for high-performance, asynchronous multi-agent orchestration.
* **AI Orchestration:** Python, FastAPI, and Pydantic.
* **LLM Inference:** Cloud-agnostic integration utilizing `LLM_SERVICE`, `LLM_MODEL`, and `LLM_API_KEY` for seamless connection to providers like Google Gemini, Anthropic Claude, or OpenAI.
* **Knowledge Graph:** Neo4j for zero-network-overhead graph traversal and data storage.
* **Frontend:** Nuxt.js v4 (Vue) and Tailwind CSS.
* **Tooling:** Bun and Nx Monorepo.

## Prerequisites

Before installation, ensure you have the following installed:

* **Bun** >= 1.1.0 ([install guide](https://bun.sh/docs/installation))
* **Go** >= 1.22 ([install guide](https://go.dev/doc/install))
* **Python** >= 3.11 ([install guide](https://www.python.org/downloads/))
* **Neo4j** >= 5.0 ([install guide](https://neo4j.com/docs/operations-manual/current/installation/))
* **Protobuf Compiler** (optional, for gRPC development)

## Installation

Clone the repository and install all dependencies:

```bash
git clone https://github.com/raihanpka/project-santara.git
cd project-santara

# Install all dependencies (Bun + Python)
make install
```

Or install components individually:

```bash
# Install Bun/Node dependencies
bun install

# Install Python AI Engine dependencies
cd apps/ai-engine
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Configuration

Copy the environment template and configure your settings:

```bash
cp apps/ai-engine/.env.example apps/ai-engine/.env
```

Edit `apps/ai-engine/.env` with your credentials:

```env
# LLM Provider: gemini, anthropic, or openai
LLM_SERVICE=gemini
LLM_MODEL=gemini-2.0-flash
LLM_API_KEY=your-api-key-here

# Neo4j Connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
```

## Local Development

Start the development servers:

```bash
# Run AI Engine (Python FastAPI)
make dev-ai

# Run Simulation Engine (Go) - in a separate terminal
make dev-sim

# Run Frontend (Nuxt.js) - in a separate terminal
make dev-frontend

# Or run all services concurrently
bun run dev
```

### Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies |
| `make dev-ai` | Run AI Engine on http://localhost:8000 |
| `make dev-sim` | Run Simulation Engine |
| `make dev-frontend` | Run Frontend on http://localhost:3000 |
| `make test` | Run all tests |
| `make test-ai` | Run Python tests with coverage |
| `make test-sim` | Run Go tests |
| `make lint` | Lint all code |
| `make proto` | Generate gRPC stubs from .proto files |
| `make clean` | Clean build artifacts |

### Data Ingestion

Ingest geographic and statistical data into the knowledge graph:

```bash
# Ingest OpenStreetMap GeoJSON data
make ingest-osm

# Ingest CSV statistical data
make ingest-bps
```

### API Documentation

Once the AI Engine is running, access the interactive API docs at:

* **Swagger UI:** http://localhost:8000/docs
* **ReDoc:** http://localhost:8000/redoc

---

## Credits & Citations

**Project Lead:**
Raihan Putra Kirana. (2026). *Project Santara: Multi-Agent GraphRAG Simulation for Agrarian Micro-Economies*. Project Concept and Developer.

**Supporting Literature:**

* **Anthropic (2025):** [How we built our multi-agent research system](https://www.anthropic.com/news/research-multi-agent-systems)
* **Yinzhu Quan and Zefang Liu (2025):** [InvAgent: A Large Language Model based Multi-Agent System for Inventory Management in Supply Chains](https://doi.org/10.48550/arXiv.2407.11384)
* **Papageorgiou, G., Sarlis, V., Maragoudakis, M., & Tjortjis, C. (2025):** [Hybrid Multi-Agent GraphRAG for E-Government: Towards a Trustworthy AI Assistant](https://doi.org/10.3390/app15116315)

## Citation

```bibtex
@misc{raihan2026projectsantara,
  author       = {Raihan Putra Kirana},
  title        = {Project Santara: Multi-Agent GraphRAG Simulation for Agrarian Micro-Economies},
  year         = {2026},
  note         = {It leverages Large Language Models (LLMs) and embedded Knowledge Graphs to model supply chain dynamics, food sovereignty, and economic resilience},
  howpublished = {\url{[https://github.com/raihanpka/project-santara](https://github.com/raihanpka/project-santara)}}
}
```

---

## License

This project is licensed under the `GNU General Public License v3.0`, see the [LICENSE](LICENSE) file for details.
