"""sim-gateway: Santara A2A router, MCP server hub, JWT auth.

Phase 1 v0.1.0: thin HTTP router. Receives A2A JSON-RPC over HTTP at
/a2a, validates a JWT bearer token, and forwards the question to
sim-id-fiskal over its /ask endpoint. Also serves an AgentCard at
/.well-known/agent-card.json.

MCP server hub is a placeholder for v0.2.0. The A2A path is the
production path for v0.1.0.
"""

from sim_gateway.main import app

__all__ = ["app"]
__version__ = "0.1.0"
