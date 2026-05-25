"""Pure handler logic — no MCP knowledge.

Keep this file framework-free so it's trivially unit-testable.
"""

from __future__ import annotations

from pydantic import BaseModel


class TemplateInput(BaseModel):
    example_input: str


class TemplateOutput(BaseModel):
    example_output: str


async def handle(payload: TemplateInput) -> TemplateOutput:
    return TemplateOutput(example_output=f"echo: {payload.example_input}")
