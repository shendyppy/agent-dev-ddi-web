"""MCP server: search_documentation."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .handler import SearchInput, handle

mcp = FastMCP("search_docs")


@mcp.tool()
async def search_documentation(query: str, top_k: int = 5) -> dict:
    """Semantic search over internal documentation.

    Use this FIRST for any user question about a product, feature, how to
    run something, or anything that might be in our docs. Retrieve evidence
    before answering.
    """
    result = await handle(SearchInput(query=query, top_k=top_k))
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
