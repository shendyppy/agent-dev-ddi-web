"""LLM client — the ONLY place in the codebase that touches LiteLLM directly.

Per ADR 0003, all LLM calls must route through this module so that:
1. Provider swapping is a single env var (LITELLM_MODEL).
2. Every call is traced to Langfuse.
3. Retry/caching/rate-limit policy lives in one place.

Do NOT import litellm or any provider SDK elsewhere in the codebase.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from typing import Any

import litellm
import tenacity
from langfuse import get_client, observe
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
)
from litellm.exceptions import (
    Timeout as LLMTimeout,
)

from .settings import settings
from .token_killer import prune_to_budget

litellm.set_verbose = False

# Transient provider errors worth retrying with backoff. Auth/validation
# errors (401/400) are deliberately excluded — retrying those only wastes the
# user's time. ServiceUnavailableError is listed explicitly because it is NOT
# a subclass of InternalServerError in LiteLLM's hierarchy.
_RETRYABLE: tuple[type[BaseException], ...] = (
    InternalServerError,  # 500 / 502 / 504
    ServiceUnavailableError,  # 503 — the "high demand" error we hit
    RateLimitError,  # 429
    APIConnectionError,  # network blips
    LLMTimeout,
)


def _log_retry(state: tenacity.RetryCallState) -> None:
    """One-line stderr note before each retry sleep, so retries show in [be] logs."""
    exc = state.outcome.exception() if state.outcome else None
    name = type(exc).__name__ if exc else "error"
    print(f"[llm] {name} on attempt {state.attempt_number}, retrying...", file=sys.stderr)


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

    # Retry transient provider errors (503/429/5xx/network) with exponential
    # backoff — lives here per this module's contract ("retry/rate-limit policy
    # in one place"). `reraise=True` surfaces the last error if every attempt
    # fails, so non-transient failures (auth, validation) still reach the
    # caller fast instead of being retried pointlessly.
    retrying = tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(settings.litellm_max_attempts),
        wait=tenacity.wait_exponential(multiplier=1, max=settings.litellm_retry_max_wait),
        retry=tenacity.retry_if_exception_type(_RETRYABLE),
        before_sleep=_log_retry,
        reraise=True,
    )
    async for attempt in retrying:
        with attempt:
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
