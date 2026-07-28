"""LLM client — the ONLY place in the codebase that touches LiteLLM directly.

Per ADR 0003, all LLM calls must route through this module so that:
1. Provider swapping is a single env var (LITELLM_MODEL).
2. Every call is traced to Langfuse.
3. Retry/caching/rate-limit policy lives in one place.

Do NOT import litellm or any provider SDK elsewhere in the codebase.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm
import tenacity
from langfuse import Langfuse, get_client, observe
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

# Langfuse is optional. With no credentials configured the SDK still spins up
# an exporter that batches spans at LANGFUSE_HOST, fails, and retries in the
# background — which is where the recurring
# "Failed to export span batch due to timeout, max retries or shutdown" line
# in the [be] log comes from. That noise buries real errors, so initialise the
# client explicitly and turn tracing off unless BOTH keys are present.
# @observe and update_current_generation stay no-ops in that state, so no
# call site needs a conditional.
_TRACING_ENABLED = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
    tracing_enabled=_TRACING_ENABLED,
)
if not _TRACING_ENABLED:
    print(
        "[llm] Langfuse tracing disabled — set LANGFUSE_PUBLIC_KEY and "
        "LANGFUSE_SECRET_KEY in .env to enable it",
        file=sys.stderr,
    )

# Transient provider errors worth retrying with backoff. Auth/validation
# errors (401/400) are deliberately excluded — retrying those only wastes the
# user's time. ServiceUnavailableError is listed explicitly because it is NOT
# a subclass of InternalServerError in LiteLLM's hierarchy.
_RETRYABLE: tuple[type[BaseException], ...] = (
    InternalServerError,  # 500 / 502 / 504
    ServiceUnavailableError,  # 503 — the "high demand" error we hit
    RateLimitError,  # 429 — but see _should_retry: a per-DAY quota is excluded
    APIConnectionError,  # network blips
    LLMTimeout,
)


def _log_retry(state: tenacity.RetryCallState) -> None:
    """One-line stderr note before each retry sleep, so retries show in [be] logs."""
    exc = state.outcome.exception() if state.outcome else None
    name = type(exc).__name__ if exc else "error"
    print(f"[llm] {name} on attempt {state.attempt_number}, retrying...", file=sys.stderr)


def is_daily_quota_error(exc: BaseException) -> bool:
    """True for a 429 that a retry cannot possibly clear.

    Not every 429 is the same. A per-MINUTE rate limit clears on its own, and
    backing off is exactly the right response. A per-DAY quota does not: it
    resets at midnight Pacific, so the backoff ladder just burns ~35 seconds of
    the user's time and then fails with the identical error.

    Gemini's free tier is the case we actually hit — the payload carries
    ``"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"`` and a
    ``retryDelay`` of ~25s, which is misleading: honouring it does nothing
    because the limit is 20 requests for the whole day, not per interval.

    Matching on the message text is unavoidable — LiteLLM flattens the provider
    payload into the exception string and exposes no structured quota field. We
    match the quota *period*, not the provider or the metric name, so this keeps
    working across providers that phrase it as "per day".
    """
    text = str(exc).lower()
    return "perday" in text or "per day" in text or "requests per day" in text


def _should_retry(exc: BaseException) -> bool:
    """Retry transient provider failures, but never an exhausted daily quota."""
    if not isinstance(exc, _RETRYABLE):
        return False
    if isinstance(exc, RateLimitError) and is_daily_quota_error(exc):
        print(
            "[llm] daily quota exhausted — not retrying (a retry cannot clear a "
            "per-day limit; it resets at midnight Pacific). Set LLM_FAKE_MODE=true "
            "in .env to keep working on the UI without the provider.",
            file=sys.stderr,
        )
        return False
    return True


# ── Offline UI mode ──────────────────────────────────────────────────
# See settings.llm_fake_mode. The fixture lives beside this module rather than
# in prompts/ because it is a canned *response*, not a prompt — nothing renders
# it through the prompt loader and it must never be shipped to a provider.

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fake_answer.md"


_FAKE_TOOL = "search_documentation"


@dataclass
class _FakeMessage:
    content: str | None
    role: str = "assistant"
    tool_calls: list[dict[str, Any]] | None = None

    def model_dump(self) -> dict[str, Any]:
        # Mirrors what graph._run_llm expects from a LiteLLM message object.
        return {"role": self.role, "content": self.content, "tool_calls": self.tool_calls}


@dataclass
class _FakeChoice:
    message: _FakeMessage
    finish_reason: str = "stop"


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice] = field(default_factory=list)


def _read_fixture() -> str:
    try:
        return _FIXTURE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return f"LLM_FAKE_MODE is on but the fixture could not be read: {exc}"


def _last_user_question(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def _first_tool_result(messages: list[dict[str, Any]]) -> str | None:
    """The content of any tool message already in this turn's history.

    Presence of ANY tool message is what moves the fake from phase 1 (ask for
    retrieval) to phase 2 (answer). That is deliberately permissive: a failed
    or empty retrieval still counts, so the fake can never request a second
    search and spin the graph until the round budget trips.
    """
    for msg in messages:
        if msg.get("role") == "tool":
            content = msg.get("content")
            return content if isinstance(content, str) else str(content)
    return None


def _extract_chunks(tool_content: str) -> tuple[list[dict[str, Any]], str | None]:
    """Dig the SearchOutput out of whatever the MCP layer handed back.

    The payload arrives as a JSON string, but the exact nesting depends on how
    the MCP client unwrapped the tool result — it can be the SearchOutput dict
    itself, a list of MCP content blocks, or a JSON string double-encoded
    inside one of those. Rather than assume one shape, walk down until a dict
    with a "chunks" key appears. Returns ([], None) if nothing matches, which
    the caller treats as "fall back to the static fixture".
    """
    seen = 0
    node: Any = tool_content
    while seen < 5:
        seen += 1
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except (json.JSONDecodeError, ValueError):
                return [], None
            continue
        if isinstance(node, list):
            if not node:
                return [], None
            # MCP content blocks: [{"type": "text", "text": "<json>"}, ...]
            first = node[0]
            node = first.get("text", first) if isinstance(first, dict) else first
            continue
        if isinstance(node, dict):
            if "chunks" in node:
                chunks = node.get("chunks") or []
                return (chunks if isinstance(chunks, list) else []), node.get("warning")
            # Some clients wrap the payload one level deeper.
            for key in ("result", "content", "output"):
                if key in node:
                    node = node[key]
                    break
            else:
                return [], None
            continue
        return [], None
    return [], None


def _render_retrieved_answer(question: str, chunks: list[dict[str, Any]], warning: str | None) -> str:
    """Compose a deterministic markdown answer out of real retrieved chunks.

    This is NOT an attempt to imitate a model. It is a readable dump of what
    retrieval actually returned, formatted the way a grounded answer is shaped
    — headings, excerpts, and a real ``Sources:`` block — so the transcript
    renders against genuine local content and genuine citations.

    Seeing the raw chunks is arguably more useful than a synthesised answer
    while working on the UI: what the retriever fed the model is exactly the
    thing you cannot see once a real model has paraphrased it.
    """
    lines: list[str] = [f"## {question or 'Hasil pencarian dokumentasi'}", ""]
    lines.append(
        f"_Jawaban dari **LLM_FAKE_MODE** — disusun dari {len(chunks)} potongan "
        "dokumentasi yang benar-benar diambil dari ChromaDB lokal, tanpa memanggil "
        "model sama sekali._"
    )
    lines.append("")

    if warning:
        lines.append(f"> **Catatan retrieval:** {warning}")
        lines.append("")

    sources: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        text = str(chunk.get("text", "")).strip()
        source = str(chunk.get("source", "unknown"))
        score = chunk.get("score")
        metadata = chunk.get("metadata") or {}
        heading = metadata.get("heading_path") or metadata.get("title") or source

        score_note = f" · skor {float(score):.3f}" if isinstance(score, (int, float)) else ""
        lines.append(f"### {i}. {heading}")
        lines.append(f"`{source}`{score_note}")
        lines.append("")
        # Excerpt rather than the whole chunk: a chunk can be a few thousand
        # characters and the point here is the shape of the transcript, not a
        # wall of text.
        excerpt = text if len(text) <= 700 else text[:700].rstrip() + "…"
        lines.append(excerpt)
        lines.append("")

        if source not in sources:
            sources.append(source)

    if sources:
        lines.append("Sources:")
        lines.extend(f"- {s}" for s in sources)

    return "\n".join(lines)


async def _fake_completion(messages: list[dict[str, Any]]) -> _FakeResponse:
    """Serve a completion with no provider call.

    Two phases when ``llm_fake_use_retrieval`` is on:

    1. No tool result in history yet → emit a ``tool_calls`` message for
       ``search_documentation``. The graph then runs the REAL MCP tool against
       the local ChromaDB index, which costs nothing and exercises the tool
       chips and message grouping in the UI.
    2. A tool result exists → compose the answer from those real chunks.

    Falls back to the static fixture whenever retrieval is off, produced no
    chunks, or returned something unparseable — so this mode still works on a
    machine that has never run ``just index``.
    """
    if settings.llm_fake_latency_seconds > 0:
        # Without a pause the reply lands in the same frame as the request and
        # the busy/typing UI never renders — which is usually the thing being
        # checked in this mode.
        await asyncio.sleep(settings.llm_fake_latency_seconds)

    if not settings.llm_fake_use_retrieval:
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=_read_fixture()))])

    tool_content = _first_tool_result(messages)

    if tool_content is None:
        question = _last_user_question(messages)
        # content=None + tool_calls is exactly what a real model emits when it
        # decides to search, so the FE renders its "searching" chip unchanged.
        # product_id is deliberately omitted: graph.call_tools overwrites it
        # with the scope the user picked, and that path should be exercised too.
        return _FakeResponse(
            choices=[
                _FakeChoice(
                    message=_FakeMessage(
                        content=None,
                        tool_calls=[
                            {
                                "id": "fake_call_search",
                                "type": "function",
                                "function": {
                                    "name": _FAKE_TOOL,
                                    "arguments": json.dumps({"query": question, "top_k": 4}),
                                },
                            }
                        ],
                    )
                )
            ]
        )

    chunks, warning = _extract_chunks(tool_content)
    if not chunks:
        print(
            "[llm] fake mode: retrieval returned no usable chunks "
            f"({warning or 'no warning'}) — falling back to the static fixture",
            file=sys.stderr,
        )
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=_read_fixture()))])

    answer = _render_retrieved_answer(_last_user_question(messages), chunks, warning)
    return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=answer))])


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

    # Checked before anything else — pruning, tracing and retry policy all
    # describe a provider call that is not going to happen.
    if settings.llm_fake_mode:
        if stream:
            raise NotImplementedError(
                "LLM_FAKE_MODE does not support stream=True. Nothing in the chat "
                "path streams tokens (server.py streams graph *nodes*), so this "
                "is unreachable from the UI."
            )
        return await _fake_completion(messages)

    if max_input_tokens is not None:
        try:
            messages = prune_to_budget(messages, max_tokens=max_input_tokens, model=model)
        except ValueError as exc:
            # The protected slice (system prompt + most recent exchange) alone
            # busts the budget — nothing left to prune. Sending the request
            # anyway is the better failure: the budget is our own cost guard,
            # well below the provider's actual context window, so the call will
            # very likely still succeed. Turning a cost heuristic into a hard
            # 500 would be worse than briefly overspending.
            print(f"[llm] token budget not enforceable: {exc}", file=sys.stderr)

    langfuse = get_client()
    langfuse.update_current_generation(model=model, input=messages)

    # Retry transient provider errors (503/per-minute 429/5xx/network) with
    # exponential backoff — lives here per this module's contract
    # ("retry/rate-limit policy in one place"). `reraise=True` surfaces the last
    # error if every attempt fails, so non-transient failures (auth, validation,
    # exhausted daily quota) still reach the caller fast instead of being
    # retried pointlessly.
    retrying = tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(settings.litellm_max_attempts),
        wait=tenacity.wait_exponential(multiplier=1, max=settings.litellm_retry_max_wait),
        retry=tenacity.retry_if_exception(_should_retry),
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
