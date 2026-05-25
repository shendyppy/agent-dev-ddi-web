"""MCP client registry.

Connects the orchestrator to all configured MCP servers (one per skill).
At startup, spawns each server as a subprocess (stdio transport) and
discovers its tools.

Per ADR 0002: skills live as MCP servers. Do not bypass this module
to call skill handlers directly.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Note: actual mcp client imports happen lazily in connect() so that
# `--list` works without the SDK fully initialized.

SERVERS_DIR = Path(__file__).resolve().parents[1] / "mcp_servers"


@dataclass
class MCPServerConfig:
    name: str
    module: str  # e.g. "mcp_servers.search_docs.server"
    env: dict[str, str] = field(default_factory=dict)


# Registry — add new skills here.
SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(name="search_docs", module="mcp_servers.search_docs.server"),
    MCPServerConfig(name="list_products", module="mcp_servers.list_products.server"),
    MCPServerConfig(
        name="capture_screenshot", module="mcp_servers.capture_screenshot.server"
    ),
    MCPServerConfig(name="check_app_health", module="mcp_servers.check_app_health.server"),
]


async def discover_all_tools() -> list[dict[str, Any]]:
    """Connect to every registered MCP server and aggregate their tool specs.

    Returns OpenAI-style tool schemas for direct use with LiteLLM.
    """
    # TODO: implement using mcp.client.stdio
    # For now, returns empty list — graph.py will get tool specs from here
    # once wired.
    return []


def _list() -> None:
    print(f"Configured MCP servers ({len(SERVERS)}):")
    for s in SERVERS:
        print(f"  - {s.name:24s}  {s.module}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP client registry inspector.")
    parser.add_argument("--list", action="store_true", help="List configured servers.")
    args = parser.parse_args()

    if args.list:
        _list()
        return

    # Default: dry-run a discovery
    tools = asyncio.run(discover_all_tools())
    print(f"Discovered {len(tools)} tools across {len(SERVERS)} servers.")


if __name__ == "__main__":
    main()
