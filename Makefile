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
	@echo "Project Santara Commands"
	@echo ""
	@echo "  make help              Show this help"
	@echo "  make install           Install all Python services and sim-kernel"
	@echo "  make test              Run all tests (Python + Go)"
	@echo "  make test-py           Run Python tests (pytest across all services)"
	@echo "  make test-go           Go tests (services/sim-engine)"
	@echo "  make test-kernel       sim-kernel tests only"
	@echo "  make lint              Lint everything"
	@echo "  make format            Format everything"
	@echo "  make build-go          Build the Go service binary"
	@echo "  make engine-test       Run sim-engine Go tests only"
	@echo "  make proto-py          Generate Python gRPC stubs from proto/simulation.proto"
	@echo "  make proto-go          Generate Go gRPC stubs from proto/simulation.proto"
	@echo "  make dataset-build     Build the Indonesia Fiscal Pressure Tracker dataset into dist/"
	@echo "  make dataset-card      Regenerate only the dataset card README.md (run once, then edit on the Hub)"
	@echo "  make dataset-push      Build the dataset and publish to raihanpka/indonesia-fiscal-pressure on the Hub"
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
			if [ -d $$svc/.venv ]; then \
				echo "  Testing $$svc (venv)..."; \
				(cd $$svc && .venv/bin/pytest -q) || exit 1; \
			else \
				echo "  Skipping $$svc (no .venv; run 'make install' first)"; \
			fi; \
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
	@if [ -d libs/sim-kernel/.venv ]; then \
		(cd libs/sim-kernel && .venv/bin/pytest -q) || exit 1; \
	else \
		echo "  libs/sim-kernel has no .venv; run 'make install' first"; \
		exit 1; \
	fi

.PHONY: lint
lint:
	@echo "Linting Python (per-service venv)..."
	@for pkg in libs/sim-kernel services/sim-id-fiskal services/sim-gateway services/sim-id-politik services/sim-id-iklim; do \
		if [ -f $$pkg/pyproject.toml ] && [ -d $$pkg/.venv ]; then \
			echo "  $$pkg..."; \
			(cd $$pkg && .venv/bin/ruff check src/ tests/ 2>/dev/null) || true; \
		fi; \
	done
	@echo "Linting Go..."
	@if [ -f services/sim-engine/go.mod ]; then \
		(cd services/sim-engine && go vet ./...) || true; \
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
		cd services/sim-engine && go build -o bin/sim-engine-server ./cmd/server && cd ../..; \
		echo "Built services/sim-engine/bin/sim-engine-server"; \
	else \
		echo "services/sim-engine not yet scaffolded"; \
	fi

.PHONY: engine-test
engine-test:
	cd services/sim-engine && go test -count=1 ./...

.PHONY: proto-py
proto-py:
	@if ! command -v protoc >/dev/null 2>&1; then \
		echo "protoc not found. Install: brew install protobuf (macOS) or apt install protobuf-compiler (Linux)"; \
		exit 1; \
	fi
	@if [ ! -d libs/sim-kernel/.venv ]; then \
		cd libs/sim-kernel && uv venv --python 3.12; \
	fi
	cd libs/sim-kernel && uv pip install grpcio grpcio-tools --quiet
	cd libs/sim-kernel && .venv/bin/python -m grpc_tools.protoc \
		--python_out=../rpc-contracts/python/sim_rpc \
		--grpc_python_out=../rpc-contracts/python/sim_rpc \
		--proto_path=../rpc-contracts/proto \
		../rpc-contracts/proto/simulation.proto
	@echo "Patching simulation_pb2_grpc.py import for package context..."
	@cd libs/rpc-contracts/python/sim_rpc && \
		sed -i.bak 's/^import simulation_pb2 as simulation__pb2$$/from . import simulation_pb2 as simulation__pb2/' simulation_pb2_grpc.py && \
		rm -f simulation_pb2_grpc.py.bak
	@echo "Generated Python stubs in libs/rpc-contracts/python/sim_rpc/"

.PHONY: proto-go
proto-go:
	@if ! command -v protoc >/dev/null 2>&1; then \
		echo "protoc not found. Install: brew install protobuf (macOS) or apt install protobuf-compiler (Linux)"; \
		exit 1; \
	fi
	@if ! command -v protoc-gen-go >/dev/null 2>&1; then \
		echo "Installing protoc-gen-go..."; \
		go install google.golang.org/protobuf/cmd/protoc-gen-go@latest; \
	fi
	@if ! command -v protoc-gen-go-grpc >/dev/null 2>&1; then \
		echo "Installing protoc-gen-go-grpc..."; \
		go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest; \
	fi
	@mkdir -p services/sim-engine/internal/grpc_gen
	cd services/sim-engine && PATH="$$(go env GOPATH)/bin:$$PATH" protoc \
		--proto_path=../../libs/rpc-contracts/proto \
		--go_out=. \
		--go_opt=paths=source_relative \
		--go-grpc_out=. \
		--go-grpc_opt=paths=source_relative \
		../../libs/rpc-contracts/proto/simulation.proto
	@if [ -f services/sim-engine/simulation.pb.go ] && [ ! -f services/sim-engine/internal/grpc_gen/simulation.pb.go ]; then \
		mv services/sim-engine/simulation.pb.go services/sim-engine/internal/grpc_gen/; \
		mv services/sim-engine/simulation_grpc.pb.go services/sim-engine/internal/grpc_gen/; \
	fi
	@echo "Generated Go stubs in services/sim-engine/internal/grpc_gen/"

.PHONY: dataset-build
dataset-build:
	@if [ ! -f libs/sim-datasets/id_fiscal_pressure/build.py ]; then \
		echo "build.py not found at libs/sim-datasets/id_fiscal_pressure/build.py"; \
		exit 1; \
	fi
	python3 libs/sim-datasets/id_fiscal_pressure/build.py

.PHONY: dataset-card
dataset-card:
	python3 libs/sim-datasets/id_fiscal_pressure/build.py --card-only

.PHONY: dataset-push
dataset-push:
	@if [ ! -f .env ]; then \
		echo ".env not found at repo root. Add HF_TOKEN=... to .env first."; \
		exit 1; \
	fi
	@if [ ! -d libs/sim-datasets/id_fiscal_pressure/dist ]; then \
		echo "dist/ does not exist. Run make dataset-build first."; \
		exit 1; \
	fi
	python3 -c "import os; from dotenv import load_dotenv; load_dotenv('.env'); \
		from huggingface_hub import HfApi; \
		api = HfApi(token=os.environ['HF_TOKEN']); \
		api.upload_folder( \
			folder_path='libs/sim-datasets/id_fiscal_pressure/dist', \
			repo_id='raihanpka/indonesia-fiscal-pressure', \
			repo_type='dataset', \
			commit_message='Sync from project-santara repo')"
	@echo "Published to raihanpka/indonesia-fiscal-pressure on the Hub"

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

.PHONY: clean-act
clean-act:
	@echo "Cleaning act cache and Docker resources..."
	-rm -rf ~/.cache/act/
	-rm -rf ~/.cache/actcache/
	-docker system prune -af > /dev/null 2>&1
	-docker volume prune -f > /dev/null 2>&1
	@echo "Act cache and Docker resources cleaned"

.PHONY: coverage
coverage:
	@echo "Installing pytest-cov in each service venv (uv pip, not .venv/bin/pip)..."
	@for pkg in libs/sim-kernel services/sim-id-fiskal services/sim-gateway services/sim-id-politik services/sim-id-iklim; do \
		if [ -f $$pkg/pyproject.toml ] && [ -d $$pkg/.venv ]; then \
			(cd $$pkg && uv pip install pytest-cov --quiet 2>/dev/null); \
		fi; \
	done
	@echo "Generating Python coverage (per service)..."
	@for pkg in libs/sim-kernel services/sim-id-fiskal services/sim-gateway services/sim-id-politik services/sim-id-iklim; do \
		if [ -f $$pkg/pyproject.toml ] && [ -d $$pkg/tests ]; then \
			echo "  $$pkg..."; \
			(cd $$pkg && .venv/bin/pytest tests/ --cov=src --cov-branch --cov-report=xml --cov-report=term-missing -q 2>&1 | tail -5); \
		fi; \
	done
	@echo "Generating Go coverage..."
	# ponytail: go test with -coverprofile invokes the covdata tool to merge
	# per-package profiles. GOTOOLDIR is not on PATH by default on most
	# runners, so we prepend it. Matches the CI workflow fix.
	cd services/sim-engine && PATH="$$(go env GOTOOLDIR):$$PATH" go test -count=1 -coverprofile=coverage.txt -covermode=set ./...
	@echo "Done. Coverage files:"
	@find . -name 'coverage.xml' -not -path '*/.venv/*' -not -path '*/node_modules/*'
	@echo "  services/sim-engine/coverage.txt"
