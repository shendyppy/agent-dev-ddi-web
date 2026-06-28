"""LLM client — the ONLY place in the codebase that touches LiteLLM directly.

Per ADR 0003, all LLM calls must route through this module so that:
1. Provider swapping is a single env var (LITELLM_MODEL).
2. Every call is traced to Langfuse.
3. Retry/caching/rate-limit policy lives in one place.

Do NOT import litellm or any provider SDK elsewhere in the codebase.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm
from langfuse import get_client, observe

from .settings import settings
from .token_killer import prune_to_budget

litellm.set_verbose = False


@observe(as_type="generation")
async def acompletion(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    stream: bool = False,
    max_input_tokens: int | None = None,
    **kwargs: Any,
) -> Any:
    """Async LLM call. Returns the LiteLLM response (or async iterator if stream=True).

    If `max_input_tokens` is set, the message list is pruned via token_killer
    before the call so the request fits within the budget.
    """
    model = model or settings.litellm_model
    if max_input_tokens is not None:
        messages = prune_to_budget(messages, max_tokens=max_input_tokens, model=model)

    langfuse = get_client()
    langfuse.update_current_generation(model=model, input=messages)

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        tools=tools,
        stream=stream,
        **kwargs,
    )

    if not stream:
        langfuse.update_current_generation(output=response)
    return response


async def astream(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    max_input_tokens: int | None = None,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Convenience wrapper for streaming responses."""
    response = await acompletion(
        messages,
        tools=tools,
        model=model,
        stream=True,
        max_input_tokens=max_input_tokens,
        **kwargs,
    )
    async for chunk in response:
        yield chunk
