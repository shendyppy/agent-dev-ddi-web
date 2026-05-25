"""MCP server entry-point for the _template skill.

Run standalone (for MCP Inspector):
    uv run python -m mcp_servers._template.server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .handler import TemplateInput, handle

mcp = FastMCP("template")


@mcp.tool()
async def template_tool(example_input: str) -> dict:
    """Example tool — replace with your skill's real description.

    The first line of this docstring becomes the tool's user-visible
    summary to the LLM. The skill.md `when_to_use` is the canonical spec;
    this docstring should mirror it.
    """
    result = await handle(TemplateInput(example_input=example_input))
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
