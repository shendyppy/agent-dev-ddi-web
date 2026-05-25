"""MCP server: check_app_health."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .handler import HealthInput, handle

mcp = FastMCP("check_app_health")


@mcp.tool()
async def check_app_health(product_id: str) -> dict:
    """Check if a product is currently running and at what URL.

    Use before suggesting the user navigate to a product.
    """
    result = await handle(HealthInput(product_id=product_id))
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
