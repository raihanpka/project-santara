# Santara Monorepo Makefile
# ========================
# This Makefile provides common development commands for the Santara project.

.PHONY: help install install-ai dev-ai test-ai lint-ai proto clean

# Default target
help:
	@echo "Santara Development Commands"
	@echo "============================"
	@echo ""
	@echo "Setup:"
	@echo "  make install        - Install all dependencies (Bun + Python)"
	@echo "  make install-ai     - Install AI Engine Python dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev-ai         - Run AI Engine in development mode"
	@echo "  make dev-sim        - Run Simulation Engine in development mode"
	@echo "  make dev-frontend   - Run Frontend in development mode"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-ai        - Run AI Engine tests"
	@echo "  make test-sim       - Run Simulation Engine tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Lint all code"
	@echo "  make lint-ai        - Lint AI Engine code"
	@echo "  make format-ai      - Format AI Engine code"
	@echo ""
	@echo "Protobuf:"
	@echo "  make proto          - Generate Go and Python stubs from .proto files"
	@echo ""
	@echo "Data:"
	@echo "  make ingest-osm     - Ingest OpenStreetMap data"
	@echo "  make ingest-bps     - Ingest BPS statistical data"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   - Build all Docker images"
	@echo "  make docker-up      - Start all services with Docker Compose"
	@echo "  make docker-down    - Stop all services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Clean build artifacts"

# =============================================================================
# Installation
# =============================================================================

install:
	@echo "Installing Bun dependencies..."
	bun install
	@echo "Installing AI Engine dependencies..."
	$(MAKE) install-ai
	@echo "Installation complete!"

install-ai:
	cd apps/ai-engine && \
	python -m venv .venv && \
	. .venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -e ".[dev]"

# =============================================================================
# Development
# =============================================================================

dev-ai:
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	uvicorn src.api.rest_router:app --reload --host 0.0.0.0 --port 8000

dev-sim:
	cd apps/sim-engine && \
	go run ./cmd/server/main.go

dev-frontend:
	cd apps/frontend && \
	bun run dev

# =============================================================================
# Testing
# =============================================================================

test: test-ai test-sim
	@echo "All tests complete!"

test-ai:
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	pytest tests/ -v --cov=src --cov-report=term-missing

test-sim:
	cd apps/sim-engine && \
	go test -v ./...

# =============================================================================
# Code Quality
# =============================================================================

lint: lint-ai lint-sim
	@echo "Linting complete!"

lint-ai:
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	ruff check src/ scripts/ && \
	mypy src/

format-ai:
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	ruff format src/ scripts/ && \
	ruff check --fix src/ scripts/

lint-sim:
	cd apps/sim-engine && \
	go vet ./... && \
	go fmt ./...

# =============================================================================
# Protobuf
# =============================================================================

PROTO_DIR := libs/rpc-contracts
PROTO_GO_OUT := libs/rpc-contracts/gen/go
PROTO_PY_OUT := libs/rpc-contracts/gen/python

proto:
	@echo "Generating protobuf stubs..."
	@mkdir -p $(PROTO_GO_OUT) $(PROTO_PY_OUT)
	protoc \
		--proto_path=$(PROTO_DIR) \
		--go_out=$(PROTO_GO_OUT) \
		--go_opt=paths=source_relative \
		--go-grpc_out=$(PROTO_GO_OUT) \
		--go-grpc_opt=paths=source_relative \
		$(PROTO_DIR)/*.proto
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	python -m grpc_tools.protoc \
		--proto_path=../../$(PROTO_DIR) \
		--python_out=../../$(PROTO_PY_OUT) \
		--grpc_python_out=../../$(PROTO_PY_OUT) \
		../../$(PROTO_DIR)/*.proto
	@echo "Protobuf stubs generated!"

# =============================================================================
# Data Ingestion
# =============================================================================

ingest-osm:
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	python -m scripts.ingest_osm --input data/osm/ --pattern "*.geojson"

ingest-bps:
	cd apps/ai-engine && \
	. .venv/bin/activate && \
	python -m scripts.ingest_bps --input data/bps/ --pattern "*.csv"

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker build -f infra/docker/Dockerfile.ai -t santara-ai-engine .
	docker build -f infra/docker/Dockerfile.go -t santara-sim-engine .

docker-up:
	docker-compose -f infra/docker/docker-compose.yml up -d

docker-down:
	docker-compose -f infra/docker/docker-compose.yml down

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "Cleaning build artifacts..."
	rm -rf apps/ai-engine/.venv
	rm -rf apps/ai-engine/__pycache__
	rm -rf apps/ai-engine/src/__pycache__
	rm -rf apps/ai-engine/.pytest_cache
	rm -rf apps/ai-engine/.mypy_cache
	rm -rf apps/ai-engine/.ruff_cache
	rm -rf apps/sim-engine/bin
	rm -rf libs/rpc-contracts/gen/go/*
	rm -rf libs/rpc-contracts/gen/python/*
	rm -rf node_modules
	@echo "Clean complete!"
