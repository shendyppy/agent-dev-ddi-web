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


# ── Picking which passages to show ───────────────────────────────────
# `search_documentation` returns a fixed `top_k` regardless of quality, so the
# tail of its list is usually a chunk that merely shares a word with the
# question. Printing it all makes the answer look thorough while burying the one
# passage that matters.
#
# The obvious filter — a similarity floor — does NOT work on this corpus, and it
# is worth recording why. Scores are `1 - chroma_distance` (see
# search_docs/handler.py), and the embedding model is `bge-small-en` against a
# largely Indonesian corpus. Measured against the real index, top-1 score:
#
#     0.501  "gimana cara menjalankan proyek ini di lokal?"     (on topic)
#     0.469  "gimana cara deploy ke staging?"                   (on topic)
#     0.514  "resep rendang padang yang enak untuk lebaran"     (OFF topic)
#     0.525  "siapa presiden pertama republik indonesia"        (OFF topic)
#
# Off-topic Indonesian outscores on-topic Indonesian, so no threshold separates
# them — an English-only model reads all Indonesian text as roughly equidistant.
# Keyword overlap does separate them cleanly on the same queries (on topic 3-10,
# off topic 0-1), so THAT is the gate, and the score is demoted to a tiebreak
# plus a floor that catches outright garbage (the English control question
# "airspeed velocity of an unladen swallow" tops out at 0.173).
#
# The real fix is a multilingual embedding model at indexing time, which is an
# ADR-sized change to indexing.py and out of scope here. Until then this keeps
# the offline answer honest rather than confidently wrong.
_MAX_ANSWER_CHUNKS = 3
_MIN_RELEVANCE_SCORE = 0.25
_RELEVANCE_GAP = 0.10
# Overlap a passage must reach to be shown at all. Two, because a hit in the
# heading counts double: one heading word is enough, or two body words. Measured
# on-topic questions clear this by a wide margin (3-10).
_MIN_KEYWORD_OVERLAP = 2

# Words that say nothing about topic. Two groups, both earned by measurement
# against the real index:
#
# 1. Grammar — what an Indonesian question spends words on regardless of subject.
# 2. How-to framing — `cara`, `bikin`, `buat`, `jelaskan`… These wrecked the
#    filter: nearly every heading in this corpus is phrased "Cara Menjalankan",
#    "Cara Membaca", "Cara Kerja", so `cara` matched everything and "gimana cara
#    bikin kopi susu yang enak" came back with a documentation page. A term that
#    appears in most documents carries no information about which one to pick.
_STOPWORDS = frozenset(
    {
        # grammar
        "yang",
        "untuk",
        "dengan",
        "dari",
        "pada",
        "adalah",
        "atau",
        "juga",
        "dan",
        "nya",
        "ada",
        "jadi",
        "agar",
        "oleh",
        "akan",
        "saat",
        "kah",
        "ini",
        "itu",
        "aku",
        "saya",
        "kita",
        "kami",
        "anda",
        # question framing
        "gimana",
        "bagaimana",
        "kalau",
        "apakah",
        "saja",
        "bisa",
        "harus",
        "mana",
        "kenapa",
        "apa",
        "siapa",
        "berapa",
        "kapan",
        "tolong",
        "jelaskan",
        "tentang",
        "punya",
        "dipakai",
        "digunakan",
        # how-to framing — see note above
        "cara",
        "caranya",
        "bikin",
        "buat",
        "buatkan",
        "membuat",
        "cari",
    }
)

# Minimum length of a token that can carry topic. Three, not four: `tep`, `cms`,
# `api`, `sso` are the product names and acronyms that matter most here, and a
# four-character floor silently dropped every one of them — "teknologi apa yang
# dipakai di TEP CMS?" scored 0.662 (the highest of any question measured) and
# still came back empty, because `tep` and `cms` were thrown away before the
# match. Two-character tokens stay out: `ke`, `di`, `ya` are pure grammar.
_MIN_WORD_LENGTH = 3


def _tokens(text: str) -> set[str]:
    """Lowercased alphanumeric tokens. Same treatment for question and passage."""
    return set("".join(c.lower() if c.isalnum() else " " for c in text).split())


def _question_words(question: str) -> set[str]:
    """Content words of the question — what :func:`_keyword_overlap` matches on."""
    return {w for w in _tokens(question) if len(w) >= _MIN_WORD_LENGTH and w not in _STOPWORDS}


def _matches(words: set[str], text: str) -> int:
    """Count question words that start a token in ``text``.

    Prefix-of-token rather than substring-of-text, and both halves matter.
    *Token* is what makes short words safe: as a bare substring `tep` also hits
    "step" and `api` hits "aplikasi", which is how an acronym filter turns into
    a random-match generator. *Prefix* is free stemming in the direction that
    actually occurs — `role` hits "roles", `lokal` hits "lokalisasi" — without
    the cost of a real stemmer.
    """
    tokens = _tokens(text)
    return sum(1 for word in words if any(token.startswith(word) for token in tokens))


def _keyword_overlap(chunk: dict[str, Any], words: set[str]) -> int:
    """How strongly this passage uses the question's own words.

    A hit in ``heading_path`` counts double. That path is the curated topic
    label a human wrote for the section, so a chunk *titled* "Menjalankan di
    lokal" is about running things locally, while a table of contents that
    merely lists the phrase in one of its cells is not. Against the real index
    those two chunks scored 0.49 and 0.50 and tied on body words — the heading
    weight is the whole reason the answer wins.
    """
    metadata = chunk.get("metadata") or {}
    heading = str(metadata.get("heading_path") or metadata.get("title") or "")
    body = str(chunk.get("text") or "")
    return 2 * _matches(words, heading) + _matches(words, body)


def _select_best_chunks(chunks: list[dict[str, Any]], question: str = "") -> list[dict[str, Any]]:
    """Narrow retrieval output to the passages actually worth showing.

    Keyword overlap is the gate and the ranking; the score is a floor and a
    tiebreak. See the block comment above for the measurements that put them in
    that order — on this corpus the score cannot tell an off-topic question from
    an on-topic one, and overlap can.

    Returns ``[]`` when nothing clears the bar. "I did not find anything close
    enough" is a real answer, and a better one than three paragraphs about
    something else — which, without a model in the loop to notice, is exactly
    what an unfiltered dump produces.

    Two deliberate escape hatches:

    - **No content words in the question** (a bare "apa itu ini?") → rank by
      score alone, keeping the best match and anything within
      :data:`_RELEVANCE_GAP`. There is nothing to overlap against, and refusing
      to answer would be worse than a weak guess.
    - **No numeric scores at all** → trust the retriever's own ordering and just
      apply the cap. A future tool that does not score must not read as an
      empty index.

    The cost of the keyword gate is a question phrased entirely in synonyms
    ("cara run aplikasi" against docs that say "menjalankan"): it gets the
    honest "sebutkan nama produk/fiturnya" note instead of the right passage.
    Accepted knowingly — with the model down, a wrong-but-confident answer is
    the more expensive failure.
    """
    scored = [
        (chunk, float(chunk["score"]))
        for chunk in chunks
        if isinstance(chunk.get("score"), (int, float)) and not isinstance(chunk.get("score"), bool)
    ]
    if not scored:
        return chunks[:_MAX_ANSWER_CHUNKS]

    scored.sort(key=lambda pair: pair[1], reverse=True)
    if scored[0][1] < _MIN_RELEVANCE_SCORE:
        return []

    words = _question_words(question)
    if not words:
        floor = max(_MIN_RELEVANCE_SCORE, scored[0][1] - _RELEVANCE_GAP)
        return [chunk for chunk, score in scored if score >= floor][:_MAX_ANSWER_CHUNKS]

    # One heading word is enough, or two body words — but a single-word question
    # can only ever reach 1 when its word sits in the body, so the bar cannot
    # exceed what the question is able to score.
    bar = min(_MIN_KEYWORD_OVERLAP, len(words))
    ranked = [
        (chunk, _keyword_overlap(chunk, words), score)
        for chunk, score in scored
        if score >= _MIN_RELEVANCE_SCORE
    ]
    ranked = [entry for entry in ranked if entry[1] >= bar]
    ranked.sort(key=lambda entry: (entry[1], entry[2]), reverse=True)
    return [chunk for chunk, _, _ in ranked][:_MAX_ANSWER_CHUNKS]


# Opening line of every offline answer. It says three things the user needs and
# cannot infer: the model is not in the loop, the text below is verbatim
# documentation rather than a paraphrase, and this is temporary.
_OFFLINE_NOTE = (
    "> Model sedang tidak bisa dihubungi (kuota atau kapasitas penuh), jadi "
    "bagian di bawah ini dikutip apa adanya dari dokumentasi kita — belum "
    "diringkas ulang. Coba tanya lagi beberapa saat lagi untuk jawaban penuh."
)


def _render_retrieved_answer(
    question: str, chunks: list[dict[str, Any]], warning: str | None
) -> str:
    """Compose a deterministic markdown answer out of real retrieved chunks.

    This is NOT an attempt to imitate a model — it quotes, it never
    paraphrases, and it says so in the first line. What it does do is give the
    passages the shape of a grounded answer (headings, excerpts, a real
    ``Sources:`` block the FE's CitationList can parse) so a degraded turn
    still reads as an answer instead of a debug dump.

    ``chunks`` is expected to be pre-filtered by :func:`_select_best_chunks`;
    this function renders whatever it is handed, in the order given.
    """
    lines: list[str] = [_OFFLINE_NOTE, ""]

    if question:
        lines.append(f"**Bagian dokumentasi yang paling dekat dengan “{question}”:**")
        lines.append("")

    numbered = len(chunks) > 1
    sources: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        text = str(chunk.get("text", "")).strip()
        source = str(chunk.get("source", "unknown"))
        score = chunk.get("score")
        metadata = chunk.get("metadata") or {}
        heading = metadata.get("heading_path") or metadata.get("title") or source

        score_note = f" · relevansi {float(score):.2f}" if isinstance(score, (int, float)) else ""
        lines.append(f"### {f'{i}. ' if numbered else ''}{heading}")
        lines.append(f"`{source}`{score_note}")
        lines.append("")
        # Excerpt rather than the whole chunk: a chunk can be a few thousand
        # characters, and past the first paragraph or two it stops answering
        # the question and starts being the rest of the page.
        excerpt = text if len(text) <= 700 else text[:700].rstrip() + "…"
        lines.append(excerpt)
        lines.append("")

        if source not in sources:
            sources.append(source)

    if warning:
        lines.append(f"> **Catatan retrieval:** {warning}")
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
    asked = f" dengan **{question}**" if question else ""
    lines = [
        "### Belum bisa dijawab sekarang",
        "",
        "Model sedang tidak bisa dihubungi (kuota atau kapasitas penuh), dan "
        f"pencarian di dokumentasi lokal tidak menemukan bagian yang cukup dekat{asked}.",
        "",
        "Yang bisa dicoba:",
        "",
        "- Tanyakan lagi beberapa saat lagi — akses ke model biasanya pulih sendiri.",
        "- Sebut nama produk atau fiturnya secara spesifik supaya pencariannya lebih tajam.",
    ]
    if warning:
        lines += ["", f"> **Catatan retrieval:** {warning}"]
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
        content = (
            _read_fixture()
            if settings.llm_fake_mode
            else _render_nothing_relevant(question, warning)
        )
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=content))])

    answer = _render_retrieved_answer(question, best, warning)
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
    # describe a provider call that is not going to happen. Either the dev
    # forced offline mode, or a recent capacity failure opened the window.
    if settings.llm_fake_mode or fallback_active():
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
    try:
        async for attempt in retrying:
            with attempt:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    tools=tools,
                    stream=stream,
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
