# Security Policy

The Project Santara maintainers take security seriously. This document explains which versions of Santara receive security updates, how to report a vulnerability, and what to expect after you report.

## Supported Versions

| Version | Supported | Notes |
|---|---|---|
| 1.x.x | Yes | Current stable line. Receives security updates. |
| 0.5.x | Yes | Receives security updates until 1.0.0 ships. |
| 0.1.x | Best effort | Receives critical security updates only. |
| Legacy apps/ code | No | The Go and Python code under apps/ predates the security policy. Migrate to services/ and libs/sim-kernel/ instead. |

## Reporting a Vulnerability

Please report security issues as a public GitHub issue.

### What to Include

A good security report includes the following.

- Description of the vulnerability and its impact
- Steps to reproduce, including a working proof of concept if possible
- Affected versions, commits, or service names
- Environment (Python version, Docker version, operating system)
- Your name and affiliation, if you want to be credited in the fix announcement
- Whether you want to disclose publicly and on what timeline

### What to Expect

1. **Within 48 hours.** Acknowledgement of your report and a confirmation that we received the report.
2. **Within 7 days.** Initial assessment, severity rating, and a plan for the fix. We may ask clarifying questions.
3. **Within 30 days.** A patched release for critical and high-severity issues. Lower-severity issues may take longer.
4. **Within 90 days.** Public disclosure of the vulnerability and the fix, coordinated with the reporter. We may delay disclosure if a coordinated disclosure is requested and the issue is not actively exploited.

If we cannot meet any of these deadlines, we will tell you why and propose a new timeline.

## Security Model

Project Santara is designed to be self-hosted. The security boundary depends on how the user deploys the platform.

- **JWT authentication** at the gateway. RS256 with rotating keys. Demo token only for local development.
- **OAuth 2.1** for the MCP server when accessed by third-party clients.
- **mTLS** for inter-service traffic in v1.0. Capability tokens in v2.0.
- **PostgreSQL per service.** No shared schema. No cross-service data access.
- **Redis Streams** for events. The outbox pattern guarantees at-least-once delivery. Consumers must be idempotent.
- **No secrets in environment variables in production.** Docker secrets or a secret manager.

## Threat Model

The following threats are in scope and actively mitigated.

- **Unauthenticated access to the gateway.** Mitigated by JWT.
- **Malicious MCP tool calls.** Mitigated by OAuth 2.1 scope, input validation via Pydantic, and rate limiting.
- **Cross-service data leakage.** Mitigated by per-service databases and the absence of cross-service joins.
- **LLM prompt injection.** Mitigated by structured output enforcement (Pydantic AI), tool scoping, and a separate "context only" MCP server for sensitive data.
- **Supply chain.** Mitigated by pinning dependencies, signed Docker images, and reproducible builds.

The following threats are out of scope and the responsibility of the operator.

- Physical access to the host machine
- Compromise of the operating system
- Compromise of the cloud provider
- Compromise of the operator's API keys for cloud LLM providers

## Known Security Advisories

None at this time.

## Acknowledgements

The following people have reported security issues responsibly. Thank you.

- (No entries yet.)

## Contact

For anything not covered here, email security@projectsantara.id.
