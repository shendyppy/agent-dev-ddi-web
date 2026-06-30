"""MCP server: capture_screenshot."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .handler import ScreenshotInput, ScreenshotOutput, handle

mcp = FastMCP("capture_screenshot")


@mcp.tool()
async def capture_screenshot(scenario: str | None = None, url: str | None = None) -> dict:
    """Capture a screenshot of the Acelents site and return its URL.

    Pass exactly one of:
      - ``scenario``: a named canonical page — "home", "tour", "plan-a-demo", "blog".
      - ``url``: any route on the site (e.g. "/tour") or an absolute URL.

    The PNG is captured by Playwright against https://dev.acelents.com and served
    at /screenshots. ALWAYS embed the returned ``screenshot_url`` in your answer
    as a markdown image — ``![<short alt>](<screenshot_url>)`` — so the user sees
    it inline. Never paste the URL as raw text. On failure, ``{"error","code"}``
    is returned; tell the user briefly and offer to retry.
    """
    try:
        result = await handle(ScreenshotInput(scenario=scenario, url=url))
    except ValueError as exc:
        # Input validation (need exactly one of scenario/url) — surface as
        # structured JSON per mcp_servers/AGENTS.md, never as an MCP exception.
        return {"error": str(exc), "code": "invalid_input"}
    return result.model_dump() if isinstance(result, ScreenshotOutput) else result


if __name__ == "__main__":
    mcp.run()
