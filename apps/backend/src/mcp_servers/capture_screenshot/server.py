"""MCP server: capture_screenshot."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .handler import ScreenshotInput, handle

mcp = FastMCP("capture_screenshot")


@mcp.tool()
async def capture_screenshot(scenario: str) -> dict:
    """Trigger a Playwright scenario and return a screenshot URL.

    Use when the user wants visual evidence of a feature.
    """
    result = await handle(ScreenshotInput(scenario=scenario))
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
