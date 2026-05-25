"""MCP server: list_products."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .handler import handle

mcp = FastMCP("list_products")


@mcp.tool()
async def list_products() -> dict:
    """List all products in the documentation catalog.

    Cheap discovery call — use when user wants to browse what's available.
    """
    result = await handle()
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
