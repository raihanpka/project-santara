# Release and Distribution

This document defines how Project Santara artifacts are versioned, packaged, and published. The strategy is still in design. Targets below are the intended channels. Implementation begins in Phase 1.

## Versioning

The project follows [Semantic Versioning](https://semver.org/).

- **Major version (X.y.z).** Breaking change to a public API, a gRPC contract, or an A2A Agent Card.
- **Minor version (x.Y.z).** New backward-compatible feature. A new sim-id service is a minor bump.
- **Patch version (x.y.Z).** Backward-compatible bug fix or documentation update.

A breaking change requires a written rationale in [CHANGELOG.md](./CHANGELOG.md). The rationale explains what broke, who is affected, and what the migration path is.

## Channels

Project Santara publishes artifacts through four channels. Each artifact has one home channel. Mirror channels are documented but not guaranteed to be in sync.

### 1. Python Package: sim-kernel on PyPI

The `sim-kernel` library is published to PyPI.

- Package name: `sim-kernel`
- Import name: `sim_kernel`
- Distribution: sdist (`.tar.gz`) and wheel (`.whl`) for Python 3.12
- Versioning: follows the sim-kernel sub-version, not the project version
- Install: `pip install sim-kernel`
- Home: https://pypi.org/project/sim-kernel/
- Mirror: GitHub Releases under [releases/tag/sim-kernel-vX.Y.Z](https://github.com/raihanpka/project-santara/releases)

### 2. Docker Images: sim-engine and Python Services on GitHub Container Registry

Each service ships a Docker image. The Go service image and the Python service images are published to GitHub Container Registry (ghcr.io).

- Registry: `ghcr.io`
- Image names:
  - `ghcr.io/raihanpka/sim-engine:X.Y.Z`
  - `ghcr.io/raihanpka/sim-gateway:X.Y.Z`
  - `ghcr.io/raihanpka/sim-id-fiskal:X.Y.Z`
  - `ghcr.io/raihanpka/sim-id-politik:X.Y.Z`
  - `ghcr.io/raihanpka/sim-id-iklim:X.Y.Z`
  - `ghcr.io/raihanpka/sim-id-agraria:X.Y.Z`
- Tags: `X.Y.Z` for releases, `latest` for the default branch, `sha-<short>` for the commit hash
- Base images:
  - Go service: `gcr.io/distroless/static-debian12` (or `alpine` if dynamic linking is needed)
  - Python services: `python:3.12-slim` for runtime, `python:3.12-slim` with dev tools for CI
- Multi-arch: `linux/amd64` and `linux/arm64`
- Vulnerability scanning: enabled via GitHub Actions on every push

### 3. Curated Datasets on Hugging Face Hub

The curated datasets (see [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) section 16) are published to the Hugging Face Hub.

- Organization: `raihanpka` (or equivalent) on Hugging Face
- Datasets: one repo per dataset
- Format: Parquet with companion `provenance.csv` and `LICENSE-DATA`
- Versioning: dataset-level semantic version, independent of the platform version
- Card: a Hugging Face dataset card with the abstract, provenance, schema, license, and citation

### 4. Go Binary: sim-engine on GitHub Releases

The Go service is also published as a static binary for users who do not run Docker.

- Asset name: `sim-engine-vX.Y.Z-<os>-<arch>.tar.gz`
- Supported: `linux/amd64`, `linux/arm64`, `darwin/amd64`, `darwin/arm64`
- Signing: cosign keyless signing with GitHub OIDC
- SBOM: CycloneDX SBOM attached to each release
- Home: https://github.com/raihanpka/project-santara/releases

## Release Process

Releases are triggered by a Git tag of the form `vX.Y.Z`. Pushing the tag triggers the release pipeline.

```
git tag vX.Y.Z
git push origin vX.Y.Z
```

The pipeline runs in this order.

1. **Lint and test.** `make lint` and `make test` must pass. No Go, no Python exception.
2. **Build artifacts.**
   - Python sdist and wheel for `sim-kernel`. Published to PyPI by trusted publishing.
   - Docker images for each service. Multi-arch build via buildx. Pushed to ghcr.io.
   - Go static binaries for each supported platform. Attached to the GitHub release.
3. **Sign and attest.** All artifacts are cosign-signed. SBOM and provenance attestations are attached.
4. **GitHub release.** A draft release is created with the changelog extracted from `CHANGELOG.md` and the artifacts attached. The release is published automatically.
5. **Documentation update.** The docs site (when it exists) is rebuilt. The Hugging Face dataset cards are updated if a dataset version changed.
6. **Announcement.** The release is announced on the configured channels. The exact channels are in CONTRIBUTING.md.

## Pre-release and Post-release

- **Pre-release.** A tag of the form `vX.Y.Z-rc.N` produces a release candidate. The artifacts are published with the `rc` suffix. PyPI rejects `rc` versions for production; they are published to TestPyPI instead.
- **Post-release.** A patch release is preferred over a yanked release. If a release is broken, a patch follows within 24 hours. If the patch is not possible, the release is yanked (PyPI) and the Docker images are marked as deprecated (ghcr.io).

## Version Compatibility

The components are versioned independently but with a compatibility matrix.

- sim-kernel X.Y.Z is compatible with services that pin to `sim-kernel>=X.Y,<X+1`.
- A service X.Y.Z is compatible with `sim-engine` X.Y.Z. Breaking the gRPC contract requires a coordinated major version bump of both.
- Datasets are versioned independently and can be regenerated against a new service version.

## Channels Not Used

The project explicitly does not use the following channels in v1.0.

- **npm registry.** The optional sim-dashboard may use it in v1.0, but it is not the primary distribution channel.
- **Docker Hub.** GitHub Container Registry is the home. Docker Hub mirror is not configured.
- **Go proxy.** Go services are not libraries. They are services. They are not published to proxy.golang.org.
- **PyPI mirror.** PyPI is the home. Mirrors are not configured.

## Why These Choices

- **PyPI for sim-kernel** because every Python service imports it. The user experience must be `pip install sim-kernel` and go.
- **GitHub Container Registry** because the project is hosted on GitHub. The integration is free. The image hosting is included.
- **Hugging Face Hub** because the datasets are public-domain data. Hub is the natural home for that community.
- **GitHub Releases for the Go binary** because static binaries are the simplest distribution for a Go service. No package manager, no registry, just a tarball.

These choices are not ideological. They are pragmatic. Any of them can change. The decision log in [docs/ROADMAP.md](./docs/ROADMAP.md) records the reasoning.
