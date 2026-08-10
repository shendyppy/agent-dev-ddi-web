"""Relevance judgement over retrieved documentation chunks.

This module answers one question: *of the passages `search_documentation`
returned, which ones actually address what the user asked?* It is deliberately
pure — no LiteLLM, no Langfuse, no settings, no I/O — so it can be unit-tested
without a model, an index, or a network, and so both callers can share it:

- :mod:`agent.llm` uses :func:`_select_best_chunks` to build the offline answer
  when the provider is unreachable.
- :mod:`agent.graph` uses :func:`rank` + :func:`confidence` to emit the
  ``retrieval`` SSE event that drives the evidence panel in the UI.

Why this is not just a similarity threshold
-------------------------------------------

The obvious filter — "keep chunks scoring above X" — does NOT work on this
corpus, and it is worth recording why so nobody reintroduces it. Scores are
``1 - chroma_distance`` (see ``mcp_servers/search_docs/handler.py``) and the
embedding model is ``bge-small-en-v1.5`` against a largely Indonesian corpus.
Measured against the real index, top-1 score:

    0.501  "gimana cara menjalankan proyek ini di lokal?"     (on topic)
    0.469  "gimana cara deploy ke staging?"                   (on topic)
    0.514  "resep rendang padang yang enak untuk lebaran"     (OFF topic)
    0.525  "siapa presiden pertama republik indonesia"        (OFF topic)

Off-topic Indonesian *outscores* on-topic Indonesian, so no threshold separates
them — an English-only model reads all Indonesian text as roughly equidistant.
Keyword overlap does separate them cleanly on the same queries (on topic 3-10,
off topic 0-1), so THAT is the gate, and the score is demoted to a tiebreak
plus a floor that catches outright garbage (the English control question
"airspeed velocity of an unladen swallow" tops out at 0.173).

The real fix is a multilingual embedding model at indexing time, which is an
ADR-sized change to ``indexing.py``: it changes vector dimensions and requires
a full ``just reindex``. Until then this keeps the answer honest rather than
confidently wrong.

How to extend
-------------

- **New signal** (e.g. recency, doc status) → compute it in :func:`_judge` and
  add a field to :class:`RankedChunk`. The FE panel renders whatever it is
  given, so a new field shows up as soon as you display it there.
- **Different thresholds** → the constants below are all measured, not guessed.
  Change one and re-run ``test_relevance.py``; several tests encode the exact
  observation that produced the current value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# ── Thresholds ───────────────────────────────────────────────────────
# Every number here was measured against the real index. The block comment in
# the module docstring explains the ordering (overlap gates, score tiebreaks).

_MAX_ANSWER_CHUNKS = 3
_MIN_RELEVANCE_SCORE = 0.25
_RELEVANCE_GAP = 0.10
# Overlap a passage must reach to be shown at all. Two, because a hit in the
# heading counts double: one heading word is enough, or two body words. Measured
# on-topic questions clear this by a wide margin (3-10).
_MIN_KEYWORD_OVERLAP = 2

# Overlap at which we call the match confident rather than merely acceptable.
# Four is two heading hits, or a heading hit plus two body words — the band
# where measured on-topic questions sat, well clear of the gate itself.
_STRONG_KEYWORD_OVERLAP = 4

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

# How much of a passage the evidence panel previews. Long enough to recognise
# the passage, short enough that eight of them do not become a wall of text.
_EXCERPT_CHARS = 240


# ── Tokenising and overlap ───────────────────────────────────────────


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


def _heading_of(chunk: dict[str, Any]) -> str:
    """The curated topic label for a chunk, falling back to its file path."""
    metadata = chunk.get("metadata") or {}
    return str(metadata.get("heading_path") or metadata.get("title") or chunk.get("source") or "")


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


# ── The verdict ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RankedChunk:
    """One retrieved passage plus the reasoning about whether to trust it.

    This is the wire shape of the ``retrieval`` SSE event (see
    ``server.py``) and therefore the contract the frontend's ``EvidencePanel``
    renders against. Both ``score`` and ``overlap`` are exposed on purpose:
    showing them side by side is what makes the failure mode legible — a user
    can see a 0.51 passage rejected for zero overlap and understand instantly
    why the score alone was never enough.
    """

    source: str
    heading: str
    score: float
    overlap: int
    #: ``strong`` = shown/answered from, ``weak`` = cleared the bar but capped,
    #: ``rejected`` = failed the score floor or the overlap gate.
    verdict: str
    excerpt: str


def _excerpt(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS].rstrip() + "…"


def _make(chunk: dict[str, Any], score: float, overlap: int, verdict: str) -> RankedChunk:
    return RankedChunk(
        source=str(chunk.get("source", "unknown")),
        heading=_heading_of(chunk),
        score=score,
        overlap=overlap,
        verdict=verdict,
        excerpt=_excerpt(chunk.get("text", "")),
    )


def _judge(chunks: list[dict[str, Any]], question: str) -> list[tuple[dict[str, Any], RankedChunk]]:
    """Rank every chunk and label it, keeping each original dict alongside.

    Pairing the verdict with the source dict is what lets
    :func:`_select_best_chunks` return the caller's own objects (the offline
    renderer needs their full text and metadata) while :func:`rank` returns
    only the display-safe projection.

    Ordering of the result: accepted passages in ranked order first, then the
    rejected ones by score. The evidence panel renders the list as given, and
    "what we used, then what we threw away" is the order that reads correctly.

    Two deliberate escape hatches, both preserved from the original
    implementation:

    - **No numeric scores at all** → trust the retriever's own ordering and just
      apply the cap. A future tool that does not score must not read as an
      empty index.
    - **No content words in the question** (a bare "apa itu ini?") → rank by
      score alone, keeping the best match and anything within
      :data:`_RELEVANCE_GAP`. There is nothing to overlap against, and refusing
      to answer would be worse than a weak guess.
    """
    words = _question_words(question)

    scored = [
        (chunk, float(chunk["score"]))
        for chunk in chunks
        if isinstance(chunk.get("score"), (int, float)) and not isinstance(chunk.get("score"), bool)
    ]

    # Escape hatch 1 — an unscored retriever.
    if not scored:
        return [
            (chunk, _make(chunk, 0.0, _keyword_overlap(chunk, words), _verdict_by_rank(i)))
            for i, chunk in enumerate(chunks)
        ]

    scored.sort(key=lambda pair: pair[1], reverse=True)

    # Nothing clears even the garbage floor — the whole result set is rejected.
    if scored[0][1] < _MIN_RELEVANCE_SCORE:
        return [
            (chunk, _make(chunk, score, _keyword_overlap(chunk, words), "rejected"))
            for chunk, score in scored
        ]

    # Escape hatch 2 — nothing to overlap against, so the score is all we have.
    if not words:
        floor = max(_MIN_RELEVANCE_SCORE, scored[0][1] - _RELEVANCE_GAP)
        accepted = [(chunk, score) for chunk, score in scored if score >= floor]
        rejected = [(chunk, score) for chunk, score in scored if score < floor]
        return [
            *(
                (chunk, _make(chunk, score, 0, _verdict_by_rank(i)))
                for i, (chunk, score) in enumerate(accepted)
            ),
            *((chunk, _make(chunk, score, 0, "rejected")) for chunk, score in rejected),
        ]

    # The normal path: overlap gates, score breaks ties.
    #
    # One heading word is enough, or two body words — but a single-word question
    # can only ever reach 1 when its word sits in the body, so the bar cannot
    # exceed what the question is able to score.
    bar = min(_MIN_KEYWORD_OVERLAP, len(words))
    graded = [(chunk, score, _keyword_overlap(chunk, words)) for chunk, score in scored]

    accepted = [entry for entry in graded if entry[1] >= _MIN_RELEVANCE_SCORE and entry[2] >= bar]
    rejected = [entry for entry in graded if entry[1] < _MIN_RELEVANCE_SCORE or entry[2] < bar]
    accepted.sort(key=lambda entry: (entry[2], entry[1]), reverse=True)

    return [
        *(
            (chunk, _make(chunk, score, overlap, _verdict_by_rank(i)))
            for i, (chunk, score, overlap) in enumerate(accepted)
        ),
        *((chunk, _make(chunk, score, overlap, "rejected")) for chunk, score, overlap in rejected),
    ]


def _verdict_by_rank(index: int) -> str:
    """``strong`` while inside the answer cap, ``weak`` once past it.

    A ``weak`` passage is not a bad match — it cleared every gate. It simply
    lost the cap, and saying so is more useful to a reader of the panel than
    silently dropping it.
    """
    return "strong" if index < _MAX_ANSWER_CHUNKS else "weak"


def rank(chunks: list[dict[str, Any]], question: str = "") -> list[RankedChunk]:
    """Public entry point: judge retrieved chunks, newest verdict first.

    Returns the display projection only — no chunk bodies beyond an excerpt,
    so the result is safe to serialise straight onto the SSE stream.
    """
    return [ranked for _, ranked in _judge(chunks, question)]


def confidence(ranked: list[RankedChunk]) -> str:
    """Summarise a ranking as one of ``high`` / ``medium`` / ``low`` / ``none``.

    Reads off the best accepted passage rather than averaging: the answer is
    built from the top passages, so a single strong match with a tail of weak
    ones is a confident answer, and averaging would hide that.

    ``none`` is a real and useful outcome — it is the state where the honest
    reply is "I did not find anything close enough", not three paragraphs about
    something else.
    """
    strong = [r for r in ranked if r.verdict == "strong"]
    if not strong:
        return "none"
    best = max(r.overlap for r in strong)
    if best >= _STRONG_KEYWORD_OVERLAP:
        return "high"
    if best >= _MIN_KEYWORD_OVERLAP:
        return "medium"
    return "low"


def _select_best_chunks(chunks: list[dict[str, Any]], question: str = "") -> list[dict[str, Any]]:
    """Narrow retrieval output to the passages actually worth showing.

    The offline answer path in :mod:`agent.llm` renders exactly what this
    returns, so it hands back the caller's original dicts (full text, full
    metadata) rather than :class:`RankedChunk` projections.

    Returns ``[]`` when nothing clears the bar. "I did not find anything close
    enough" is a real answer, and a better one than three paragraphs about
    something else — which, without a model in the loop to notice, is exactly
    what an unfiltered dump produces.

    The cost of the keyword gate is a question phrased entirely in synonyms
    ("cara run aplikasi" against docs that say "menjalankan"): it gets the
    honest "sebutkan nama produk/fiturnya" note instead of the right passage.
    Accepted knowingly — with the model down, a wrong-but-confident answer is
    the more expensive failure.
    """
    return [chunk for chunk, ranked in _judge(chunks, question) if ranked.verdict == "strong"]


# ── Reading the tool payload ─────────────────────────────────────────


def extract_chunks(tool_content: str) -> tuple[list[dict[str, Any]], str | None]:
    """Dig the SearchOutput out of whatever the MCP layer handed back.

    The payload arrives as a JSON string, but the exact nesting depends on how
    the MCP client unwrapped the tool result — it can be the SearchOutput dict
    itself, a list of MCP content blocks, or a JSON string double-encoded
    inside one of those. Rather than assume one shape, walk down until a dict
    with a "chunks" key appears. Returns ([], None) if nothing matches, which
    callers treat as "there is nothing to rank".
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


__all__ = [
    "RankedChunk",
    "confidence",
    "extract_chunks",
    "rank",
]
