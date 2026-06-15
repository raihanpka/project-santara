# Project Santara: Makefile
#
# This Makefile is intentionally simple. Each service has its own pyproject.toml
# or go.mod. This root Makefile provides convenience targets for working
# across the whole monorepo.
#
# Anti-pattern: do not turn this into a monorepo build tool. The decision log in
# docs/ROADMAP.md explicitly says "no monorepo build tool in v1.0."

.PHONY: help
help:
	@echo "Project Santara - convenience targets"
	@echo ""
	@echo "  make help              Show this help"
	@echo "  make install           Install all Python services and sim-kernel"
	@echo "  make test              Run all tests (Python + Go)"
	@echo "  make test-py           Run Python tests (pytest across all services)"
	@echo "  make test-go           Run Go tests (services/sim-engine)"
	@echo "  make test-kernel       Run sim-kernel tests only"
	@echo "  make lint              Lint everything"
	@echo "  make format            Format everything"
	@echo "  make build-go          Build the Go service binary"
	@echo "  make docker-up         Bring up docker compose stack"
	@echo "  make docker-down       Tear down docker compose stack"
	@echo "  make clean             Remove build artifacts and caches"

.PHONY: install
install:
	@echo "Installing sim-kernel..."
	cd libs/sim-kernel && pip install -e ".[dev]"
	@echo ""
	@echo "Installing Python services (those that exist)..."
	@for svc in services/sim-gateway services/sim-id-fiskal services/sim-id-politik services/sim-id-iklim services/sim-id-agraria; do \
		if [ -f $$svc/pyproject.toml ]; then \
			echo "  Installing $$svc..."; \
			cd $$svc && pip install -e ".[dev]" && cd ../..; \
		else \
			echo "  Skipping $$svc (no pyproject.toml yet)"; \
		fi; \
	done

.PHONY: test
test: test-py test-go

.PHONY: test-py
test-py: test-kernel
	@for svc in services/sim-gateway services/sim-id-fiskal services/sim-id-politik services/sim-id-iklim services/sim-id-agraria; do \
		if [ -f $$svc/pyproject.toml ] && [ -d $$svc/tests ]; then \
			echo "  Testing $$svc..."; \
			cd $$svc && pytest && cd ../..; \
		fi; \
	done

.PHONY: test-go
test-go:
	@if [ -f services/sim-engine/go.mod ]; then \
		echo "  Testing services/sim-engine..."; \
		cd services/sim-engine && go test ./... && cd ../..; \
	fi

.PHONY: test-kernel
test-kernel:
	@echo "  Testing libs/sim-kernel..."
	cd libs/sim-kernel && pytest

.PHONY: lint
lint:
	@echo "Linting Python..."
	cd libs/sim-kernel && ruff check src/ tests/ || true
	@for svc in services/sim-*; do \
		if [ -f $$svc/pyproject.toml ]; then \
			cd $$svc && ruff check src/ tests/ 2>/dev/null || true && cd ../..; \
		fi; \
	done
	@echo "Linting Go..."
	@if [ -f services/sim-engine/go.mod ]; then \
		cd services/sim-engine && golangci-lint run 2>/dev/null || true && cd ../..; \
	fi

.PHONY: format
format:
	@echo "Formatting Python..."
	cd libs/sim-kernel && ruff format src/ tests/ 2>/dev/null || true
	@for svc in services/sim-*; do \
		if [ -f $$svc/pyproject.toml ]; then \
			cd $$svc && ruff format src/ tests/ 2>/dev/null || true && cd ../..; \
		fi; \
	done
	@echo "Formatting Go..."
	@if [ -f services/sim-engine/go.mod ]; then \
		cd services/sim-engine && gofmt -w . && cd ../..; \
	fi

.PHONY: build-go
build-go:
	@if [ -f services/sim-engine/go.mod ]; then \
		cd services/sim-engine && go build -o bin/sim-engine ./cmd/server && cd ../..; \
		echo "Built services/sim-engine/bin/sim-engine"; \
	else \
		echo "services/sim-engine not yet scaffolded"; \
	fi

.PHONY: docker-up
docker-up:
	docker compose up

.PHONY: docker-down
docker-down:
	docker compose down

.PHONY: clean
clean:
	@echo "Removing build artifacts..."
	rm -rf libs/sim-kernel/.pytest_cache
	rm -rf libs/sim-kernel/.ruff_cache
	rm -rf libs/sim-kernel/.mypy_cache
	rm -rf libs/sim-kernel/*.egg-info
	rm -rf libs/sim-kernel/build
	rm -rf libs/sim-kernel/dist
	@for svc in services/sim-*; do \
		rm -rf $$svc/.pytest_cache $$svc/.ruff_cache $$svc/.mypy_cache $$svc/*.egg-info $$svc/build $$svc/dist; \
	done
	rm -rf services/sim-engine/bin
	@echo "Clean complete"
