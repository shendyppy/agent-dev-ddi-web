"""MCP client registry — connects the orchestrator to every skill server.

Per ADR 0002, **skills live as MCP servers**, one folder per skill under
``apps/backend/src/mcp_servers/<name>/``. This module is the orchestrator's
side of that contract: it knows how to spawn each server, ask it what tools
it exposes, and route LLM tool calls to the right server.

How a request flows through here
--------------------------------

::

    graph.py call_llm
        ↓ asks for the tool catalogue
    discover_all_tools()        ←─── caches the result; first call spawns
        ↓ returns OpenAI-style       every registered server briefly to
        ↓ tool specs                 read its tool list, then closes them
    LLM picks a tool and emits a tool_call
        ↓
    graph.py call_tools
        ↓ for each tool_call
    call_tool(name, arguments)  ←─── spawns the owning server, runs the
        ↓ returns the JSON-ish       call, returns the result, closes
        ↓ result                     the server
    graph.py appends a "tool" message and loops back to the LLM

Why spawn-per-call instead of a long-lived pool
-----------------------------------------------

Each call costs ~500 ms of subprocess startup. For a doc chatbot at our
expected QPS that is acceptable, and the code stays trivial — no lifespan
management, no exit stacks, no "what happens when a child crashes" plumbing.

If latency ever matters more than simplicity, swap :func:`call_tool` for a
session pool using ``contextlib.AsyncExitStack`` keyed by server name. The
public surface (``discover_all_tools`` + ``call_tool``) does not need to
change. Worth an ADR when that day comes.

How to extend
-------------

- **Add a skill** → append a :class:`MCPServerConfig` entry to
  :data:`SERVERS` and let :func:`discover_all_tools` pick it up next run.
  See ``apps/backend/src/mcp_servers/AGENTS.md`` for the full new-skill
  checklist.
- **Pass an API key to a server** → use the ``env`` field on
  :class:`MCPServerConfig`. The server will see it as a normal
  environment variable.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ─── Paths used to spawn servers ─────────────────────────────────────────
# Servers are spawned via ``python -m mcp_servers.<name>.server`` with the
# backend's ``src/`` directory on PYTHONPATH (mirrors how uvicorn is run
# with ``--app-dir src``). Doing it this way means the spawn inherits the
# active virtualenv automatically — no need to hardcode a uv command.

BACKEND_DIR = Path(__file__).resolve().parents[2]  # apps/backend/
SRC_DIR = BACKEND_DIR / "src"


# ─── Server registry ─────────────────────────────────────────────────────


@dataclass
class MCPServerConfig:
    """Where the orchestrator can find one MCP server.

    Fields:

    - ``name`` — short identifier used in logs and registry keys. Should
      match the folder name under ``mcp_servers/``.
    - ``module`` — Python dotted path of the server entry point. Always
      ``mcp_servers.<folder>.server`` for in-repo servers.
    - ``env`` — extra env vars to set in the child process (API keys,
      feature flags). Inherited env is still passed; this dict overlays.
    """

    name: str
    module: str
    env: dict[str, str] = field(default_factory=dict)


# Append new servers here. Order does not matter — discovery is independent
# per server. Keep one entry per folder under mcp_servers/ that exposes
# tools intended for the agent (skip ``_template`` — it's a scaffold).
SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(name="search_docs", module="mcp_servers.search_docs.server"),
    MCPServerConfig(name="list_products", module="mcp_servers.list_products.server"),
    MCPServerConfig(
        name="capture_screenshot", module="mcp_servers.capture_screenshot.server"
    ),
    MCPServerConfig(
        name="check_app_health", module="mcp_servers.check_app_health.server"
    ),
]


# ─── Internal: spawn one server, hand back an MCP ClientSession ──────────


def _server_params(config: MCPServerConfig) -> StdioServerParameters:
    """Build the StdioServerParameters that will spawn this server.

    Using ``sys.executable`` keeps us on whatever Python the orchestrator
    is already running with (the uv-managed venv when launched via
    ``just dev-be``). PYTHONPATH gets ``src/`` prepended so the server's
    own imports resolve from the same source tree.
    """
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SRC_DIR) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    )
    env.update(config.env)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", config.module],
        env=env,
    )


# ─── Discovery: build the OpenAI-style tool catalogue ────────────────────
# Cached at module level. The first orchestrator call (typically the first
# user message) pays the discovery cost (~500ms × number of servers); every
# request after that hits the cache. Restart the backend to refresh.

_tool_cache: list[dict[str, Any]] | None = None
_tool_owner: dict[str, str] = {}  # tool_name → server name (for routing)


def _mcp_tool_to_openai(server_name: str, tool: Any) -> dict[str, Any]:
    """Convert an MCP ``Tool`` to the OpenAI/LiteLLM function-call schema.

    LiteLLM passes whatever ``tools=[...]`` we give it straight through to
    the provider, so we use the format Claude and OpenAI both understand:
    a list of ``{type: "function", function: {name, description,
    parameters}}`` entries.

    We also remember which server owns this tool name so :func:`call_tool`
    can route the dispatch later. If two servers exposed the same tool
    name we would silently overwrite the mapping — keep tool names unique.
    """
    _tool_owner[tool.name] = server_name
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            # MCP exposes the schema as ``inputSchema``; OpenAI expects
            # ``parameters``. Fall back to an empty object when a tool
            # declares no inputs.
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


async def _discover_one(config: MCPServerConfig) -> list[dict[str, Any]]:
    """Spawn one server briefly and list its tools.

    Errors are caught and logged rather than raised — one broken skill
    should not take down the whole catalogue. The user-visible effect is
    that the LLM simply will not see that skill's tools.
    """
    try:
        async with stdio_client(_server_params(config)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                return [_mcp_tool_to_openai(config.name, t) for t in listed.tools]
    except Exception as exc:  # noqa: BLE001 — broad catch is intentional here
        print(f"[mcp_clients] discovery failed for {config.name!r}: {exc}", file=sys.stderr)
        return []


async def discover_all_tools(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return the flat OpenAI-style tool catalogue across every server.

    Cached after the first call. Pass ``force_refresh=True`` to rebuild —
    useful in tests or when a skill was added mid-session.
    """
    global _tool_cache
    if _tool_cache is not None and not force_refresh:
        return _tool_cache

    _tool_owner.clear()
    tools: list[dict[str, Any]] = []
    for config in SERVERS:
        tools.extend(await _discover_one(config))

    _tool_cache = tools
    return tools


# ─── Dispatch: call one tool by name and return the result ───────────────


async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Execute ``name(**arguments)`` on whichever MCP server owns the tool.

    Raises ``KeyError`` if the tool is not in the discovery cache — that
    means the LLM hallucinated a tool name and the caller should surface
    the error back to the LLM as a tool error so it self-corrects.

    The MCP SDK wraps successful tool returns in a structured object with
    ``content`` (a list of text/image/resource parts). For most of our
    skills the content is a single text block holding a JSON-serialised
    Pydantic model — we return it as-is so the caller can json-decode and
    feed straight back to the LLM.
    """
    if not _tool_owner:
        await discover_all_tools()  # populate the routing map on first use

    server_name = _tool_owner.get(name)
    if server_name is None:
        raise KeyError(
            f"tool {name!r} is not registered — available: {sorted(_tool_owner)}"
        )

    config = next(s for s in SERVERS if s.name == server_name)
    async with stdio_client(_server_params(config)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            # Convert MCP content parts to a single string for the LLM.
            # Each part has a ``type`` ("text", "image", ...); for now we
            # only handle text. Add cases here when a skill starts
            # returning images / resources.
            parts: list[str] = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                else:
                    parts.append(str(content))
            return "\n".join(parts) if parts else ""


# ─── CLI: handy for "is the registry working at all?" checks ─────────────


def _list_cli() -> None:
    print(f"Configured MCP servers ({len(SERVERS)}):")
    for s in SERVERS:
        print(f"  - {s.name:24s}  {s.module}")


async def _discover_cli() -> None:
    tools = await discover_all_tools(force_refresh=True)
    print(f"Discovered {len(tools)} tool(s) across {len(SERVERS)} server(s):")
    for t in tools:
        fn = t["function"]
        owner = _tool_owner.get(fn["name"], "?")
        print(f"  - {fn['name']:30s} ({owner})")


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP client registry inspector.")
    parser.add_argument("--list", action="store_true", help="List configured servers (fast).")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Spawn each server and print the discovered tool catalogue (slower).",
    )
    args = parser.parse_args()

    if args.list:
        _list_cli()
        return
    if args.discover:
        asyncio.run(_discover_cli())
        return
    parser.print_help()


if __name__ == "__main__":
    main()
