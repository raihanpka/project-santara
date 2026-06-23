# Project Santara

[![CI](https://github.com/raihanpka/project-santara/actions/workflows/ci.yml/badge.svg)](https://github.com/raihanpka/project-santara/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/raihanpka/project-santara/branch/main/graph/badge.svg)](https://codecov.io/gh/raihanpka/project-santara)
[![Go Report Card](https://goreportcard.com/badge/github.com/raihanpka/project-santara/services/sim-engine)](https://goreportcard.com/report/github.com/raihanpka/project-santara/services/sim-engine)
[![Go Reference](https://pkg.go.dev/badge/github.com/raihanpka/project-santara/services/sim-engine.svg)](https://pkg.go.dev/github.com/raihanpka/project-santara/services/sim-engine)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](./libs/sim-kernel/pyproject.toml)

An open-source counterfactual microservices platform for simulating Indonesia's economic, political, and climate systems. Python services handle language-model reasoning and protocol exposure. A Go service runs the simulation tick engine. A shared Python library called sim-kernel provides the domain models and protocol helpers.

For the Indonesian version, see [PANDUAN.md].

---

## Services

| Service | Language | Protocol | Port | Purpose |
| --- | --- | --- | --- | --- |
| sim-gateway | Python 3.12 | HTTP (A2A JSON-RPC) | 8000 | Routes anchor questions to sim-id services. JWT auth (HS256 with aud and iss). |
| sim-engine | Go 1.22 | gRPC | 50052 | Tick engine and world state. The performance tier. |
| sim-id-fiskal | Python 3.12 | HTTP (REST) | 8001 | Fiscal stress test. Pass-through model with curated Pertamax, Pertalite, and Solar prices. |
| sim-id-politik | Python 3.12 | HTTP (REST) | 8002 | Political dynamics. Pass-through MBG swing voter model for 2029. |
| sim-id-iklim | Python 3.12 | HTTP (REST) | 8003 | Climate emergency. Pass-through karhutla haze model for Riau. |

Three more sim-id services (agraria, sosial, moneter) are planned for v0.5.0+.

---

## To start using Santara

The fastest way is Docker. The full stack comes up with one command.

```bash
git clone https://github.com/raihanpka/project-santara
cd project-santara
make docker-up
```

After docker-up, the services are reachable at:

- sim-gateway at http://localhost:8000 (A2A JSON-RPC at POST /a2a)
- sim-id-fiskal at http://localhost:8001 (OpenAPI docs included)
- sim-engine (Go gRPC) at localhost:50052

To ask the first anchor question against the running stack:

```bash
curl -X POST http://localhost:8000/a2a \
  -H "Authorization: Bearer $(python -c 'import jwt,time; print(jwt.encode({"sub":"test"}, "ponytail: dev only, replace in prod", algorithm="HS256"))')" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"ask","params":{"question":"Apa yang terjadi ke inflasi kalau Pertamax naik 30 persen lagi?"}}'
```

To use sim-kernel as a Python library in another application:

```bash
pip install sim-kernel
```

To pull the v0.1.0 container images directly from GHCR:

```bash
docker pull ghcr.io/raihanpka/project-santara/sim-engine:0.1.0
docker pull ghcr.io/raihanpka/project-santara/sim-gateway:0.1.0
docker pull ghcr.io/raihanpka/project-santara/sim-id-fiskal:0.1.0
```

For the full story, head over to the [architecture documentation] or the [Indonesian front door][PANDUAN.md].

---

## To start developing Santara

The repository is a hybrid microservices layout. Python services live in `services/`. The Go service lives in `services/sim-engine/`. Shared Python code lives in `libs/sim-kernel/`. Protobuf contracts live in `libs/rpc-contracts/`. Curated datasets live in `libs/sim-datasets/`.

If you want to build the whole thing right away there are two options.

##### You have a working Go environment and Python 3.12 with uv.

```bash
git clone https://github.com/raihanpka/project-santara
cd project-santara
make install
make test
```

The `make install` target installs sim-kernel and every Python service that has a `pyproject.toml`. The `make test` target runs the Python test suite, the Go test suite, and the Python integration test against the Go binary.

##### You only have a working Docker environment.

```bash
git clone https://github.com/raihanpka/project-santara
cd project-santara
make build-go
docker compose up
```

For the full story, head over to the [architecture documentation] and the [contributors guide][CONTRIBUTING.md].

---

## Support

If you need support, start with the [troubleshooting guide] in the architecture docs, and work your way through the process.

That said, if you have questions or find a bug, open an [issue]. If you want to propose a change, open a draft pull request early to get feedback.

---

## Documentation

The full documentation set is in the `docs/` directory. The most important files:

- [docs/ARCHITECTURE.md] - canonical architecture, service map, tech stack
- [docs/ROADMAP.md] - phased roadmap, decision log
- [docs/AGENTS.md] - guidance for AI coding assistants
- [docs/COMMIT_STYLE.md] - commit message convention
- [CONTRIBUTING.md] - contributor guide (code style, PR process)
- [PANDUAN.md] - Indonesian front door
- [CHANGELOG.md] - release history

The curated dataset for the first anchor question is published on the Hugging Face Hub at [raihanpka/indonesia-fiscal-pressure](https://huggingface.co/datasets/raihanpka/indonesia-fiscal-pressure).

---

## Contributing

We welcome contributions in code, documentation, translation, scenarios, bug reports, and feature proposals. The full contributor guide is in [CONTRIBUTING.md]. The short version:

1. Read the [Code of Conduct][CONTRIBUTING.md#code-of-conduct]
2. Read [docs/ARCHITECTURE.md] and [docs/ROADMAP.md]
3. Look for [issues] labeled `good first issue` or `help wanted`
4. Open a draft pull request early to get feedback
5. Run the full test suite before requesting review

---

## License

Project Santara is licensed under the Apache License 2.0. The full license text is in the [LICENSE] file at the repository root. The Apache 2.0 license includes an explicit patent grant, allows commercial use, and requires preservation of the copyright notice and the license terms in any redistribution.

---

## Citation

If you use Project Santara in academic work, please cite the platform as follows.

```bibtex
@misc{project-santara-2026,
  author = {Raihan Putra Kirana},
  title  = {Project Santara: An Open-Source Counterfactual Microservices Platform for Simulating Indonesia's Economic, Political, and Climate Systems},
  year   = {2026},
  url    = {https://github.com/raihanpka/project-santara}
}
```

For datasets hosted on the Hugging Face Hub, cite the dataset card directly. Each dataset card includes a citation block with the source URLs and the version of the loader that produced it.

[CHANGELOG.md]: ./CHANGELOG.md
[CONTRIBUTING.md]: ./CONTRIBUTING.md
[LICENSE]: ./LICENSE
[PANDUAN.md]: ./docs-id/PANDUAN.md
[architecture documentation]: ./docs/ARCHITECTURE.md
[docs/AGENTS.md]: ./docs/AGENTS.md
[docs/ARCHITECTURE.md]: ./docs/ARCHITECTURE.md
[docs/ROADMAP.md]: ./docs/ROADMAP.md
[docs/COMMIT_STYLE.md]: ./docs/COMMIT_STYLE.md
[CONTRIBUTING.md#code-of-conduct]: ./CONTRIBUTING.md#code-of-conduct
[troubleshooting guide]: ./docs/ARCHITECTURE.md#operational-concerns
[issue]: https://github.com/raihanpka/project-santara/issues
[issues]: https://github.com/raihanpka/project-santara/issues
[raihanpka/indonesia-fiscal-pressure]: https://huggingface.co/datasets/raihanpka/indonesia-fiscal-pressure
