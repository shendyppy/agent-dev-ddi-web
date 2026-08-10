"""RAG retrieval over the ChromaDB index built by ``agent.indexing``.

This is the *handler* — a pure async function. ``server.py`` next door
wraps it as an MCP tool; the handler itself is happy to be unit-tested
without any MCP machinery.

How a query flows through here
------------------------------

::

    1. LLM emits a tool_call for search_documentation(query, top_k).
    2. orchestrator (graph.py → mcp_clients.call_tool) dispatches over
       stdio to this server.
    3. server.py validates inputs with SearchInput (Pydantic).
    4. handle() embeds the query with fastembed (same model used at
       index time — they MUST match or distances are meaningless).
    5. Chroma's persistent client runs an ANN search against the
       precomputed chunk embeddings and returns top-k.
    6. We re-shape the Chroma result into our Chunk list and hand it
       back. The LLM then quotes the chunks and cites their sources.

Why we embed the query ourselves instead of letting Chroma do it
----------------------------------------------------------------

Chroma can accept ``query_texts=[...]`` and embed internally — but only if
the collection was created with an ``embedding_function=`` argument. We
chose not to do that in ``indexing.py`` because hiding the embedder inside
the collection makes "which model produced these vectors?" invisible at the
call site. Doing it explicitly here keeps the contract obvious: same
``EMBEDDING_MODEL_NAME`` constant, both sides.

How to extend
-------------

- **Filter by product** → accept a ``product_id`` argument and pass it as
  ``where={"product_id": product_id}`` to ``collection.query``. The
  metadata is already on every chunk.
- **Add a reranker** → run ``collection.query`` with a larger ``n_results``
  than ``top_k``, then call a cross-encoder over the candidates and trim.
  Documented as the next upgrade in ADR 0004.
- **Switch embedding model** → update ``EMBEDDING_MODEL_NAME`` here AND in
  ``agent.indexing``, then run ``just reindex``. Mismatched models silently
  return garbage rankings.
"""

from __future__ import annotations

# Local imports of orchestrator-side modules are forbidden in MCP servers
# (per mcp_servers/AGENTS.md). Read the persistence dir straight from the
# env var that ``agent.settings`` exposes, with a default that matches the
# Settings default — keeps the server runnable standalone.
import os
from pathlib import Path
from typing import Any

from chromadb import PersistentClient
from fastembed import TextEmbedding
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[5]
CHROMA_PERSIST_DIR = Path(os.environ.get("CHROMA_PERSIST_DIR", ".data/chroma"))
if not CHROMA_PERSIST_DIR.is_absolute():
    # Anchored to the repo root, never the cwd. This server runs as a
    # subprocess and inherits the orchestrator's working directory, so a
    # cwd-relative path silently split the index in two: `just index` (which
    # cd's into apps/backend) wrote one, anything started from the repo root
    # read another — see agent.settings.resolve_from_repo_root.
    CHROMA_PERSIST_DIR = (_REPO_ROOT / CHROMA_PERSIST_DIR).resolve()

# Must match agent.indexing.EMBEDDING_MODEL_NAME — they're separate
# constants on purpose (each module is independently runnable) but they
# need to be kept in sync. If you change one, change the other and reindex.
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME = "docs"


# ─── Public schema (the LLM-facing contract) ─────────────────────────────


class SearchInput(BaseModel):
    """Inputs the LLM passes when it calls ``search_documentation``.

    ``top_k`` is bounded so a hallucinated huge value can't blow up the
    retrieval cost or the context window of the next LLM call.
    """

    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    # When set, retrieval is restricted to chunks tagged with this product_id
    # (the metadata written by agent.indexing). Leave None to search the whole
    # corpus. This is the knob the product picker uses to scope answers.
    product_id: str | None = None


class Chunk(BaseModel):
    """One retrieved piece of documentation.

    Fields:

    - ``text`` — the chunk body the LLM will read and quote.
    - ``source`` — the relative path the chunk came from. Used for the
      ``Sources:`` line the agent appends to every grounded answer.
    - ``score`` — relevance (higher is better). Chroma returns a
      *distance* (lower is better); we convert so the field name matches
      what consumers expect everywhere else.
    - ``metadata`` — passthrough of any extra fields the indexer stored
      (``product_id``, ``heading_path``, ``status``...). Lets the LLM
      filter or cite by section.
    """

    text: str
    source: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchOutput(BaseModel):
    """What ``search_documentation`` returns to the LLM.

    ``warning`` is non-None when retrieval ran but produced something the
    caller should know about — e.g. "index hasn't been built yet". The
    LLM is instructed (in ``prompts/system/main-agent.md``) to read this
    field and behave accordingly rather than silently fabricating an
    answer.
    """

    chunks: list[Chunk]
    warning: str | None = None


# ─── Internal: lazy singletons for the embedder and client ───────────────
# Both are expensive to construct (model download, on-disk handle) but
# cheap to reuse. Module-level globals keep the cost paid once per server
# subprocess lifetime. Since each tool call spawns a fresh subprocess
# today, that's "per call" — acceptable. When we move to a session pool
# (see mcp_clients.py docstring), these become true singletons across
# many calls.

_embedder: TextEmbedding | None = None
_client: PersistentClient | None = None


def _get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _embedder


def _get_client() -> PersistentClient:
    global _client
    if _client is None:
        _client = PersistentClient(path=str(CHROMA_PERSIST_DIR))
    return _client


# ─── Handler ─────────────────────────────────────────────────────────────


async def handle(payload: SearchInput) -> SearchOutput:
    """Run one semantic search over the docs collection.

    Returns an empty result + warning when the index hasn't been built
    yet — the LLM should then either ask the user to run ``just index``
    or refuse to answer rather than hallucinating.
    """
    if not CHROMA_PERSIST_DIR.exists():
        return SearchOutput(
            chunks=[],
            warning=(
                "the documentation index has not been built yet — run `just index` and try again"
            ),
        )

    client = _get_client()
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:  # noqa: BLE001 — Chroma raises a bare Exception here
        # ``get_collection`` raises if the named collection is absent.
        # That maps to the same "no index" experience for the LLM.
        return SearchOutput(
            chunks=[],
            warning=(
                f"collection {COLLECTION_NAME!r} does not exist yet — run `just index` to build it"
            ),
        )

    if collection.count() == 0:
        return SearchOutput(chunks=[], warning="the documentation index is empty")

    # fastembed's ``embed`` is a generator; we only need one vector here.
    [query_vec] = list(_get_embedder().embed([payload.query]))

    # Chroma returns parallel arrays under ``ids``/``documents``/etc. with
    # an outer list per query (we only sent one query → take index [0]).
    # Scope to a single product when asked. Chroma's ``where`` runs the
    # metadata filter *before* the ANN search, so a scoped query never even
    # considers other products' chunks.
    where = {"product_id": payload.product_id} if payload.product_id else None
    raw = collection.query(
        query_embeddings=[query_vec.tolist()],
        n_results=payload.top_k,
        where=where,
    )
    ids = raw.get("ids", [[]])[0]
    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0] or [{} for _ in ids]
    distances = raw.get("distances", [[]])[0] or [0.0 for _ in ids]

    chunks: list[Chunk] = []
    for doc, meta, dist in zip(documents, metadatas, distances, strict=False):
        meta = dict(meta or {})
        source = str(meta.pop("source", "unknown"))
        # Chroma distance for the default L2/cosine space is "lower is
        # better". Most callers expect "higher is better" relevance, so
        # we flip with 1 - distance. Values can go negative if the
        # underlying space allows it; that is informative, don't clip.
        score = float(1.0 - dist)
        chunks.append(Chunk(text=doc, source=source, score=score, metadata=meta))

    # An empty result has to say so out loud. Returning bare `chunks=[]` reads
    # to the LLM as "the search ran and there was nothing to report", which is
    # exactly the condition under which it starts filling gaps from memory —
    # the failure mode main-agent.md v7 was written to stop. It also matters
    # more now that the orchestrator hard-scopes searches to one product: an
    # empty result is far more often "wrong product" than "no such doc", and
    # the agent can only say that if we tell it which scope was applied.
    if not chunks:
        if payload.product_id:
            return SearchOutput(
                chunks=[],
                warning=(
                    f"no documentation matched this query within product "
                    f"{payload.product_id!r} — the search was scoped to that product. "
                    "Tell the user you found nothing for it there and suggest they "
                    "switch focus; do not answer from general knowledge."
                ),
            )
        return SearchOutput(
            chunks=[],
            warning="no documentation matched this query across any product",
        )

    return SearchOutput(chunks=chunks)
