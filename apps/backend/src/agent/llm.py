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
import os
import re
import sys
import time
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

from .relevance import _select_best_chunks, extract_chunks
from .settings import settings
from .token_killer import prune_to_budget

# Re-exported under its private name because test_llm.py and the offline
# renderer below both grew up with it here. The logic itself now lives in
# agent.relevance, which agent.graph also uses to build the evidence panel
# payload — one judgement, two consumers, no drift.
_extract_chunks = extract_chunks

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
            "per-day limit; it resets at midnight Pacific). Falling back to the "
            "local index instead.",
            file=sys.stderr,
        )
        return False
    return True


# ── Automatic offline fallback ───────────────────────────────────────
# The provider is not reliably there. The Gemini free tier is capped at 20
# requests per DAY per model (429) and the cheap tiers throw 503 "high demand"
# under load; both used to reach the browser as a red error bubble, because the
# retry ladder above only helps when capacity returns within ~35 seconds.
#
# So when a call fails for a *capacity* reason and the retries are spent, we
# stop raising and answer from the local ChromaDB index instead. There is
# nothing to configure: the window below starts closed and is opened by
# :func:`_enter_fallback` at the moment the provider says no.
#
# Only capacity errors qualify. An auth failure (401), a malformed request
# (400) or a retired model id (404) must still surface loudly — degrading those
# into a plausible-looking answer would hide a misconfiguration for hours.
#
# The window is time-boxed rather than sticky so the process heals itself: the
# next turn after it lapses tries the real provider again. A per-minute 429 or
# a 503 usually clears in seconds, so it gets a short window; an exhausted
# per-day quota does not clear until midnight Pacific, so probing it more than
# every half hour is pure waste.

_FALLBACK_WINDOW_TRANSIENT = 120.0  # seconds — 503 / per-minute 429 / network
_FALLBACK_WINDOW_DAILY_QUOTA = 1800.0  # seconds — per-day quota exhausted

# Monotonic deadline while the provider is being skipped; None = normal service.
# Module state on purpose: the policy belongs to this gateway (see the module
# docstring), and every request in the process shares one provider quota.
_fallback_deadline: float | None = None


def is_capacity_error(exc: BaseException) -> bool:
    """True when the provider refused because of load, quota or reachability.

    Deliberately the same set as :data:`_RETRYABLE`: those are exactly the
    failures that say "not now" rather than "you asked wrongly". Connection
    errors and timeouts are in it too — from the user's seat "the model is
    swamped" and "the model is unreachable" are the same event, and both are
    better served by a grounded local answer than by a stack trace.
    """
    return isinstance(exc, _RETRYABLE)


def _enter_fallback(exc: BaseException) -> None:
    """Open the offline window after a capacity failure."""
    global _fallback_deadline
    window = (
        _FALLBACK_WINDOW_DAILY_QUOTA
        if isinstance(exc, RateLimitError) and is_daily_quota_error(exc)
        else _FALLBACK_WINDOW_TRANSIENT
    )
    _fallback_deadline = time.monotonic() + window
    print(
        f"[llm] {type(exc).__name__} — provider unavailable, answering from the "
        f"local index for the next {window:.0f}s",
        file=sys.stderr,
    )


def fallback_active() -> bool:
    """True while provider calls are being skipped. Self-clearing on expiry."""
    global _fallback_deadline
    if _fallback_deadline is None:
        return False
    if time.monotonic() >= _fallback_deadline:
        _fallback_deadline = None
        print("[llm] offline window lapsed — trying the provider again", file=sys.stderr)
        return False
    return True


def reset_fallback() -> None:
    """Close the offline window immediately. For tests and manual recovery."""
    global _fallback_deadline
    _fallback_deadline = None


# ── Answering without the provider ───────────────────────────────────
# Reached automatically via the window above, or forced by
# settings.llm_fake_mode during UI work. The fixture lives beside this module
# rather than in prompts/ because it is a canned *response*, not a prompt —
# nothing renders it through the prompt loader and it must never be shipped to
# a provider.

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fake_answer.md"


_FAKE_TOOL = "search_documentation"

# Candidate pool for the offline path. Wider than the three passages that can be
# shown, on purpose: _select_best_chunks eliminates most of what comes back, so
# a pool the size of the output leaves it nothing to choose from. Measured at
# 4 vs 8 vs 12 on the real index — going 4 → 8 replaced two off-topic passages
# with the right sections on "cara menjalankan di lokal" and changed nothing for
# off-topic questions (still rejected), while 12 added nothing 8 had not already
# found. Retrieval is local and free, so the only cost is a slightly larger tool
# result in the transcript.
_FAKE_TOOL_TOP_K = 8


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


# Opening line of every offline answer. It says three things the user needs and
# cannot infer: the model is not in the loop, the text below is verbatim
# documentation rather than a paraphrase, and this is temporary. Phrased for a
# teammate, not an operator — "kuota atau kapasitas penuh" and other
# infrastructure vocabulary stays out of the transcript.
_OFFLINE_NOTE = (
    "> **Mode offline** — Model sedang tidak bisa dihubungi, jadi untuk "
    "sementara jawaban ini diambil langsung dari dokumentasi kita dan dikutip "
    "apa adanya. Coba tanya lagi beberapa saat lagi ya untuk jawaban yang "
    "sudah dirangkum."
)


_EXCERPT_BUDGET = 700


def _strip_leading_heading(text: str) -> str:
    """Drop a chunk's own leading markdown heading line(s).

    The index splits documents ON their headings, so a chunk's first line is
    usually the same title we already print via ``heading_path`` — leaving it
    in rendered the title twice, once as our ``###`` and once as the doc's own
    ``##`` (bigger than ours, so the hierarchy even looked inverted).
    """
    lines = text.lstrip().split("\n")
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines)


def _close_open_fence(text: str) -> str:
    """Append a closing ``` when ``text`` ends inside a fenced code block.

    An unclosed fence is the worst markdown breakage this renderer can emit:
    everything AFTER it — our own ``###`` section headings, tables, the lot —
    is swallowed into one giant code block, and the transcript shows raw
    markdown in a monospace box. It happens two ways: :func:`_excerpt` cuts a
    chunk before its fence closes, or the indexer split the source document
    mid-fence so the chunk arrives already unbalanced. Both end here.
    """
    if len(re.findall(r"(?m)^ {0,3}```", text)) % 2 == 1:
        return text + "\n```"
    return text


def _excerpt(text: str, budget: int = _EXCERPT_BUDGET) -> str:
    """Shorten a chunk so that what remains is still VALID markdown.

    Chunks are markdown themselves — headings, GFM tables, numbered lists,
    fenced code blocks. The old hard cut at ``budget`` characters is what made
    offline answers look broken in the transcript: chop a table mid-row and
    the unbalanced pipes stop parsing as a table at all, so the user sees raw
    ``|`` soup.

    Boundary preference: paragraph, then line, then word. The line boundary
    is the load-bearing one — cutting a table between rows just drops rows,
    which still renders as a (shorter) table. Whatever survives the cut is
    passed through :func:`_close_open_fence`, because a cut that lands inside
    a ``` block would otherwise turn the entire rest of the answer into code.
    """
    if len(text) <= budget:
        return _close_open_fence(text)
    cut = text.rfind("\n\n", 0, budget)
    if cut <= 0:
        cut = text.rfind("\n", 0, budget)
    if cut <= 0:
        cut = text.rfind(" ", 0, budget)
    if cut <= 0:
        cut = budget
    # The ellipsis gets its own paragraph OUTSIDE any reopened fence, so it
    # reads as "the doc continues" rather than gluing itself onto whatever
    # block happened to be last.
    return _close_open_fence(text[:cut].rstrip()) + "\n\n…"


def _render_retrieved_answer(
    question: str, chunks: list[dict[str, Any]], warning: str | None
) -> str:
    """Compose a deterministic markdown answer out of real retrieved chunks.

    This is NOT an attempt to imitate a model — it quotes, it never
    paraphrases, and it says so in the first line. What it does do is give the
    passages the shape of a grounded answer (headings, excerpts, a real
    ``Sources:`` block the FE's CitationList can parse) so a degraded turn
    still reads as an answer instead of a debug dump.

    Pipeline internals stay OUT of the prose on purpose:

    - No similarity scores. They mean nothing to the reader, and ours are
      structurally unreliable anyway — the embedding model is English while
      the corpus is Indonesian, so the numbers cannot separate on-topic from
      off-topic and printing them just invites wrong conclusions.
    - No raw path under each heading. The ``Sources:`` block at the end
      already carries every path, and the FE renders those as citation chips;
      repeating them inline made the answer read like a debug dump.

    ``chunks`` is expected to be pre-filtered by :func:`_select_best_chunks`;
    this function renders whatever it is handed, in the order given.
    """
    lines: list[str] = [_OFFLINE_NOTE, ""]

    if question:
        lines.append(f"Ini bagian dokumentasi yang paling relevan dengan “{question}”:")
        lines.append("")

    numbered = len(chunks) > 1
    sources: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        # Normalize Windows line endings: the corpus is indexed on Windows, so
        # chunk text can carry \r\n. Left alone it breaks twice — _excerpt's
        # paragraph-boundary search looks for "\n\n" and never finds one, and
        # the FE's markdown parser drops CRLF tables to raw per-row paragraphs.
        text = str(chunk.get("text", "")).replace("\r\n", "\n").replace("\r", "\n").strip()
        source = str(chunk.get("source", "unknown"))
        metadata = chunk.get("metadata") or {}
        heading = metadata.get("heading_path") or metadata.get("title") or source

        lines.append(f"### {f'{i}. ' if numbered else ''}{heading}")
        lines.append("")
        # Excerpt rather than the whole chunk: a chunk can be a few thousand
        # characters, and past the first paragraph or two it stops answering
        # the question and starts being the rest of the page.
        lines.append(_excerpt(_strip_leading_heading(text)))
        lines.append("")

        if source not in sources:
            sources.append(source)

    if warning:
        lines.append(f"> **Catatan:** {warning}")
        lines.append("")

    if sources:
        lines.append("Sources:")
        lines.extend(f"- {s}" for s in sources)

    return "\n".join(lines)


def _render_nothing_relevant(question: str, warning: str | None) -> str:
    """Answer for "the model is down AND the index has nothing close".

    The honest dead end. It must not be the static fixture: that document is a
    markdown showcase for UI work, and serving it to a real user as an answer
    would be a lie dressed up as thoroughness.
    """
    asked = f" dengan “{question}”" if question else ""
    lines = [
        "### Belum bisa dijawab sekarang",
        "",
        "Model sedang tidak bisa dihubungi, dan aku juga belum menemukan bagian "
        f"dokumentasi yang cukup dekat{asked}.",
        "",
        "Yang bisa kamu coba:",
        "",
        "- Tanya lagi beberapa saat lagi — biasanya akses ke model pulih sendiri.",
        "- Sebutkan nama produk atau fiturnya biar pencariannya lebih tajam.",
    ]
    if warning:
        lines += ["", f"> **Catatan:** {warning}"]
    return "\n".join(lines)


async def _fake_completion(messages: list[dict[str, Any]]) -> _FakeResponse:
    """Serve a completion with no provider call.

    Two phases when ``llm_fake_use_retrieval`` is on:

    1. No tool result in history yet → emit a ``tool_calls`` message for
       ``search_documentation``. The graph then runs the REAL MCP tool against
       the local ChromaDB index, which costs nothing and exercises the tool
       chips and message grouping in the UI.
    2. A tool result exists → answer from the best of those real chunks.

    When retrieval yields nothing usable the two callers want different things,
    so they get different endings: a forced ``llm_fake_mode`` run gets the
    static fixture (the point there is rendering, and it must work on a machine
    that has never run ``just index``), while a real outage gets an honest
    "nothing close enough" note.
    """
    if settings.llm_fake_mode and settings.llm_fake_latency_seconds > 0:
        # Only for the forced dev mode: without a pause the reply lands in the
        # same frame as the request and the busy/typing UI never renders, which
        # is usually the thing being checked. A genuine outage has already
        # spent seconds failing and retrying, so it needs no help looking slow.
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
                                    "arguments": json.dumps(
                                        {"query": question, "top_k": _FAKE_TOOL_TOP_K}
                                    ),
                                },
                            }
                        ],
                    )
                )
            ]
        )

    question = _last_user_question(messages)
    chunks, warning = _extract_chunks(tool_content)
    best = _select_best_chunks(chunks, question)

    if not best:
        print(
            f"[llm] offline answer: retrieval gave nothing relevant enough "
            f"({len(chunks)} chunk(s), {warning or 'no warning'})",
            file=sys.stderr,
        )
        # The fixture is for ONE situation: forced dev mode on a machine whose
        # index is missing or empty, where the point is markdown rendering and
        # there is nothing real to render. Gating it on `llm_fake_mode` alone was
        # too broad — with a real index present, an off-topic question served the
        # fixture, so the transcript showed a confident markdown showcase sitting
        # directly above an evidence panel reporting "nothing matched". Two parts
        # of the same turn contradicting each other is worse than either failure
        # on its own.
        #
        # Retrieval having returned chunks is what distinguishes the two: it
        # means the index is there and simply had nothing close enough, which is
        # a real answer and deserves the honest note in both modes.
        content = (
            _read_fixture()
            if settings.llm_fake_mode and not chunks
            else _render_nothing_relevant(question, warning)
        )
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=content))])

    answer = _render_retrieved_answer(question, best, warning)
    return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=answer))])


# ── Credential resolution ────────────────────────────────────────────
# Per ADR 0010. Until now nothing in this codebase passed an api_key to
# LiteLLM at all: `settings.py` declared three `*_api_key` fields that were
# never read, and authentication happened only because `import litellm` calls
# `load_dotenv()`, which finds the repo-root `.env` and loads the WHOLE file
# into os.environ. That worked, but it is invisible at the call site, it drags
# unrelated secrets (Supabase service-role key included) into the process
# environment, and it cannot express a per-request credential at all — which is
# exactly what bring-your-own-key needs.


def _provider_of(model: str) -> str | None:
    """LiteLLM's provider name for a model string, or None if it cannot tell.

    ``get_llm_provider`` is the same resolution LiteLLM uses internally to pick
    a transport, so asking it keeps our env-var naming in step with whatever the
    library expects. Verified against gemini, anthropic, deepseek, dashscope
    (Qwen) and openrouter.

    Never raises: an unrecognised model must fall through to the generic key
    rather than break the call before it is even attempted.
    """
    try:
        _, provider, _, _ = litellm.get_llm_provider(model=model)
        return str(provider) if provider else None
    except Exception:  # noqa: BLE001 — a bad model id is the provider's error to report
        return None


def resolve_api_key(model: str, user_key: str | None = None) -> str | None:
    """Pick the credential for one call. See ADR 0010 for the ordering.

    1. ``user_key`` — supplied per request by the browser (BYOK).
    2. ``<PROVIDER>_API_KEY`` — e.g. ``GEMINI_API_KEY``, ``DEEPSEEK_API_KEY``.
       Keeps several providers credentialed at once, which is what makes a
       runtime model picker possible.
    3. ``MODEL_API_KEY`` — generic fallback, so swapping provider is two lines
       in ``.env`` with no vendor-specific variable name to remember.
    4. ``None`` — pass nothing and let LiteLLM do its own env lookup.

    Layer 4 is what makes this change backwards compatible: with no key
    configured anywhere the caller behaves exactly as it did before.

    Layers 2-4 are NOT optional niceties. Evals and CI run headless with no user
    to paste anything, so a user-key-only design would break ``just eval``.
    """
    if user_key and user_key.strip():
        return user_key.strip()

    provider = _provider_of(model)
    if provider:
        # os.environ, not settings: the set of provider variables is open-ended
        # (LiteLLM ships 141 providers) and enumerating them as Settings fields
        # is what produced the three dead fields this ADR removes.
        from_provider = os.environ.get(f"{provider.upper()}_API_KEY")
        if from_provider:
            return from_provider

    return settings.model_api_key or None


# capture_input/capture_output are OFF, and that is a security control, not a
# tuning knob.
#
# `@observe` captures the decorated function's arguments by default — the flag
# resolves from LANGFUSE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED, which defaults to
# "True", and _get_input_from_func_args serialises **kwargs wholesale. Since
# `api_key` is a kwarg here, every BYOK call on a Langfuse-enabled deployment
# would have written the user's credential into a trace, where it persists
# outside this process. That is the exact leak ADR 0010 exists to close, and it
# was invisible: the first test only asserted on update_current_generation,
# which is the OTHER way input reaches a trace.
#
# Nothing is lost by turning it off — the two calls below set `input` and
# `output` explicitly and deliberately, with the credential excluded.
@observe(as_type="generation", capture_input=False, capture_output=False)
async def acompletion(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    stream: bool = False,
    max_input_tokens: int | None = None,
    api_key: str | None = None,
    offline: bool = False,
    **kwargs: Any,
) -> Any:
    """Async LLM call. Returns the LiteLLM response (or async iterator if stream=True).

    If `max_input_tokens` is set, the message list is pruned via token_killer
    before the call so the request fits within the budget.

    `api_key` is the caller's per-request credential (BYOK). It is resolved
    through :func:`resolve_api_key`, passed to the provider, and never logged,
    traced or stored — see ADR 0010.

    `offline` skips the provider for THIS call only. It is the per-request twin
    of ``settings.llm_fake_mode``, and the distinction matters: the setting is
    process-global, so exposing it as a UI toggle would let one person switch
    the model off for everyone sharing the deployment. Per-request, one user's
    choice affects only their own turns. The env var stays as the process-wide
    default because evals and CI need exactly that.
    """
    model = model or settings.litellm_model

    # Checked before anything else — pruning, tracing and retry policy all
    # describe a provider call that is not going to happen. Either this caller
    # asked to stay offline, the deployment forced it, or a recent capacity
    # failure opened the window.
    if offline or settings.llm_fake_mode or fallback_active():
        if stream:
            raise NotImplementedError(
                "Offline mode does not support stream=True. Nothing in the chat "
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

    # Resolved after the offline check: an offline turn makes no provider call,
    # so there is no credential to pick and nothing to leak.
    resolved_key = resolve_api_key(model, api_key)

    langfuse = get_client()
    # `model` and `messages` only — never the credential. Langfuse persists what
    # it is given, so a key that reaches a trace is a key written to durable
    # storage outside this process. ADR 0010 lists this as one of three leak
    # paths; test_llm.py asserts it stays closed.
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
    try:
        async for attempt in retrying:
            with attempt:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    tools=tools,
                    stream=stream,
                    # Omitted entirely when unresolved, rather than passed as
                    # None: an explicit api_key=None on some providers short
                    # circuits LiteLLM's own env lookup instead of deferring to
                    # it, which would break the pre-ADR-0010 behaviour this
                    # layer promises to preserve.
                    **({"api_key": resolved_key} if resolved_key else {}),
                    **({"api_base": settings.model_api_base} if settings.model_api_base else {}),
                    **kwargs,
                )
    except Exception as exc:
        # Retries are spent (or the error was never worth retrying). If the
        # provider is simply out of capacity, degrade instead of failing: open
        # the offline window and answer this same turn from the local index.
        # Anything else — auth, validation, a retired model id — must surface.
        if stream or not is_capacity_error(exc):
            raise
        _enter_fallback(exc)
        return await _fake_completion(messages)

    if not stream:
        langfuse.update_current_generation(output=response)
    return response


async def astream(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    max_input_tokens: int | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Convenience wrapper for streaming responses."""
    response = await acompletion(
        messages,
        tools=tools,
        model=model,
        stream=True,
        max_input_tokens=max_input_tokens,
        api_key=api_key,
        **kwargs,
    )
    async for chunk in response:
        yield chunk
