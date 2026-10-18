"""MCP tool-server entrypoint (AgentCore Runtime).

Runs the allowlisted, scope-enforced tools as a stateless streamable-HTTP MCP
server on ``0.0.0.0:8000/mcp`` — the contract AgentCore Runtime expects for MCP
protocol runtimes. All AWS data permissions live on THIS runtime's execution
role; the agents hold none, so tools are reachable only through this server and
only by the agent roles granted InvokeAgentRuntime on it.

    python -m src.mcp_server.main
"""

from __future__ import annotations

from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.mcp_server.server import build_tools_from_settings, create_mcp_server

logger = get_logger(__name__)


def main() -> None:  # pragma: no cover - process entrypoint
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.scope_signing_secret:
        raise RuntimeError("SCOPE_SIGNING_SECRET is required for the MCP server")

    tools = build_tools_from_settings(settings)
    server = create_mcp_server(tools, scope_secret=settings.scope_signing_secret)
    logger.info("mcp_server_starting")
    # AgentCore MCP contract: stateless streamable-HTTP at 0.0.0.0:8000/mcp.
    server.run(transport="streamable-http")


if __name__ == "__main__":  # pragma: no cover
    main()
