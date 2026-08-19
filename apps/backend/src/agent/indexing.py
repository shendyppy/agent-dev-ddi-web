"""ChromaDB indexer — the RAG corpus builder.

This module is run via ``just index``. It walks every documentation source we
care about, splits each file into retrievable chunks, embeds the chunks with
fastembed (a Rust-backed ONNX runner — no API key, no cost), and persists
them to ChromaDB on disk at ``.data/chroma/``.

It is the canonical reference for *how* RAG ingestion works in this repo. If
you ever need to index a new corpus (a different folder, a different file
type), copy this file's *shape* — discover → chunk → embed → upsert.

Where this fits in the bigger picture
-------------------------------------

::

    indexing.py  (this file, run ad-hoc)         ──upserts──▶  ChromaDB
                                                                  │
    search_docs MCP server (handler.py)          ──queries──────▶ │
                                                                  ▼
    LangGraph agent (graph.py) ──tool_call──▶ search_docs ──▶ chunks ──▶ LLM

Decisions encoded here (do not change without an ADR):

- **Vector store** = ChromaDB persistent client → see ADR 0004.
- **Embedding model** = fastembed ``BAAI/bge-small-en-v1.5`` → see ADR 0004.
- **Chunking** = MarkdownHeaderTextSplitter first (so chunks respect section
  boundaries), then RecursiveCharacterTextSplitter to cap chunk size. See ADR
  0004 for the ~800-token / 100-overlap target.
- **Chunk ID** = deterministic ``"<source>::<chunk_index>"`` so re-running
  ``just index`` is idempotent. Stale chunks from deleted source files are
  pruned at the end of each run.
- **Indexed sources** = (1) top-level docs (``architecture.md``, the
  catalog), (2) per-product docs under ``docs/products/`` (the canonical
  format described in ``PRODUCT-DOC-FORMAT.md``), (3) the legacy free-form
  ``docs/knowledge-base/`` corpus — kept indexed during/after the Path B
  retirement (ADR 0007) so PortrAI users do not lose answers while we reshape
  that content into the product format, and (4) the external ``tep-web``
  source corpus (the Acelents website) under ``settings.tep_web_root``,
  ingested as the ``acelents`` product via :func:`chunk_code_file`.

How to extend
-------------

- **Index a new folder** → add it to :data:`SOURCE_DISCOVERERS`.
- **Change chunk size** → adjust :data:`CHUNK_TARGET_CHARS` /
  :data:`CHUNK_OVERLAP_CHARS` (keep the ADR in sync).
- **Swap embedding model** → change :data:`EMBEDDING_MODEL_NAME` and re-run
  ``just reindex`` (full drop + rebuild — embeddings from different models
  are not interchangeable).
- **Swap vector store** (e.g. to Qdrant) → write a new ADR first, then
  rewrite :func:`build_index` against the new client. The chunking + metadata
  logic above the upsert call should remain unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter
from chromadb import PersistentClient
from chromadb.api.models.Collection import Collection
from fastembed import TextEmbedding
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from .settings import REPO_ROOT, settings

# ─── Constants ────────────────────────────────────────────────────────────
# These are the knobs you might tune. Bigger changes belong in an ADR.

DOCS_ROOT = REPO_ROOT / "docs"
PRODUCTS_DIR = DOCS_ROOT / "products"
KNOWLEDGE_BASE_DIR = DOCS_ROOT / "knowledge-base"

# fastembed model. Quality "good enough" for technical docs; upgrade path
# (Voyage / OpenAI) is documented in ADR 0004.
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# ChromaDB collection name. One collection per logical corpus. We only have
# one corpus today; if we ever isolate per-product retrieval, give each
# product its own collection here.
COLLECTION_NAME = "docs"

# Chunk size targets. ADR 0004 specifies ~800 tokens / 100 overlap. We
# express that in characters because the splitter is character-based, using
# the ~4-chars-per-token rule of thumb for cl100k_base.
CHUNK_TARGET_CHARS = 3200
CHUNK_OVERLAP_CHARS = 400

# Heading-level boundaries the markdown splitter respects. We treat h1–h3
# as section boundaries; deeper headings (h4+) stay inline so micro-sections
# don't fragment.
MARKDOWN_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


# ─── Source discovery ────────────────────────────────────────────────────
# Each discoverer returns a list of files to index. Add a new function here
# (and append it to SOURCE_DISCOVERERS below) to bring a new corpus online.


def discover_top_level_docs() -> list[Path]:
    """Repo-level docs the agent should be able to answer about itself.

    These are not per-product — they describe the system as a whole.
    """
    candidates = [
        DOCS_ROOT / "product-catalog.md",
        DOCS_ROOT / "architecture.md",
    ]
    return [p for p in candidates if p.exists()]


def discover_product_docs() -> list[Path]:
    """Every ``.md`` under ``docs/products/`` except the ``_template`` folder.

    The template would otherwise pollute retrieval with literal placeholder
    text ("e.g., Node 22+, Python 3.11+"). Skip it explicitly.
    """
    if not PRODUCTS_DIR.exists():
        return []
    return [p for p in PRODUCTS_DIR.rglob("*.md") if "_template" not in p.parts]


def discover_knowledge_base() -> list[Path]:
    """The legacy free-form corpus the old PortrAI path used.

    Indexed as-is until it gets reshaped into the per-product format (ADR
    0007 tracks this as follow-up, not a blocker). Without this discoverer,
    every PortrAI answer would silently degrade after the cutover.
    """
    if not KNOWLEDGE_BASE_DIR.exists():
        return []
    return list(KNOWLEDGE_BASE_DIR.glob("*.md"))


def discover_tep_web_source() -> list[Path]:
    """Source code of the Acelents website (the external ``tep-web`` repo).

    Indexed as the ``acelents`` product so the agent can answer code-level
    questions about how the site is built (routes, components, tech stack) —
    not just the curated prose under ``docs/products/acelents/``. External to
    ``REPO_ROOT`` on purpose: it is a separate project we ingest, located at
    ``settings.tep_web_root`` (override via the ``TEP_WEB_ROOT`` env var).

    Walks ``apps/src/**/*.{astro,tsx,ts}``, skipping generated/build dirs.
    Returns an empty list when ``tep_web_root`` is absent, so a checkout
    without the external repo still indexes the rest of the corpus instead of
    crashing. The external path is why these files go through
    :func:`chunk_code_file` rather than the markdown-centric :func:`chunk_file`
    (whose ``_relative_source`` would raise ``ValueError`` outside the repo).
    """
    root = settings.tep_web_root
    if not root.exists():
        return []
    src = root / "apps" / "src"
    if not src.exists():
        return []
    skip_parts = {"dist", ".astro", "node_modules"}
    files: list[Path] = []
    for pattern in ("*.astro", "*.tsx", "*.ts"):
        for p in src.rglob(pattern):
            if not skip_parts.isdisjoint(p.parts):
                continue
            files.append(p)
    return files


SOURCE_DISCOVERERS: list[Callable[[], list[Path]]] = [
    discover_top_level_docs,
    discover_product_docs,
    discover_knowledge_base,
    discover_tep_web_source,
]


# ─── Chunking ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndexedChunk:
    """One row destined for ChromaDB.

    Kept as a frozen dataclass (not a Pydantic model) because nothing crosses
    a process boundary here — this is internal-only data flowing into the
    upsert call. Pydantic would just add ceremony.
    """

    chunk_id: str
    text: str
    metadata: dict[str, Any]


def _relative_source(path: Path) -> str:
    """Stable string identifier for a source file (used in chunk IDs).

    Always relative to ``REPO_ROOT`` and POSIX-style — so the same chunk
    keeps the same ID across Windows / macOS / Linux contributors.
    """
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _slugify(text: str) -> str:
    """Lowercase + hyphenate a string into a stable product id.

    ``"PortrAI CMS (copy)"`` → ``"portrai-cms-copy"``. Used as the fallback
    id for knowledge-base files that don't declare one in frontmatter, so the
    same file always maps to the same product_id across reindex runs.
    """
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def _infer_product_id(path: Path, fm_metadata: dict[str, Any]) -> str | None:
    """Resolve the product id for a source file.

    Resolution order (first hit wins):

    1. Frontmatter ``product_id:`` or ``id:`` — authoritative. PRODUCT-DOC-FORMAT
       requires it for product docs; knowledge-base files may opt in to a clean
       id this way (recommended for nice display/filtering).
    2. ``docs/products/<id>/…`` — the folder name *is* the id (handles
       ``runbook.md`` and other frontmatter-less files under a product folder).
    3. ``docs/knowledge-base/<file>.md`` — the slug of the filename, so each
       legacy free-form file becomes its own selectable "product" with zero
       manual setup. Add frontmatter (rule 1) when you want a tidier id.

    Anything else (catalog, architecture) has no product scope → None.
    """
    for key in ("product_id", "id"):
        value = fm_metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    try:
        rel_parts = path.resolve().relative_to(PRODUCTS_DIR).parts
        # Only a file *inside* a product folder (docs/products/<id>/…) counts.
        # A loose .md directly under products/ (e.g. AGENTS.md, the format
        # guide) is not a product and must not leak into the picker.
        if len(rel_parts) >= 2:
            return rel_parts[0]
    except ValueError:
        pass
    try:
        path.resolve().relative_to(KNOWLEDGE_BASE_DIR)
        return _slugify(path.stem)
    except ValueError:
        pass
    return None


def _infer_product_name(path: Path, fm_metadata: dict[str, Any], body: str) -> str:
    """Human-readable product label shown in the UI picker.

    Resolution order: frontmatter ``product_name``/``name`` → the document's
    first ``# H1`` heading → a title-cased version of the filename. We never
    return empty so the picker chip always has something to render.
    """
    for key in ("product_name", "name"):
        value = fm_metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    h1 = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    if h1:
        return h1.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _clean_metadata(raw: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Chroma rejects None and non-scalar metadata values.

    Strip Nones, coerce lists → comma-joined strings (so ``tags`` still
    becomes queryable text), and drop anything else that isn't a primitive.
    """
    out: dict[str, str | int | float | bool] = {}
    for k, v in raw.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = ", ".join(str(item) for item in v)
        else:
            out[k] = str(v)
    return out


def chunk_file(path: Path) -> list[IndexedChunk]:
    """Split one markdown file into RAG-ready chunks.

    Two-pass split:

    1. **MarkdownHeaderTextSplitter** breaks the document at h1/h2/h3
       boundaries and attaches the heading path as metadata. This is what
       lets us cite "Section X > Subsection Y" later.
    2. **RecursiveCharacterTextSplitter** further breaks any oversized
       section into ~3200-char windows with 400-char overlap, so the LLM
       always gets coherent context blocks even when one section is huge.

    Metadata attached to every chunk:

    - ``source``: POSIX-relative path (for citations and chunk ID).
    - ``product_id``: when scoped to a specific product.
    - Plus any allowlisted frontmatter fields (``name``, ``status``,
      ``owner``, ``default_url``, ``health_check``, ``tags``, ...).
    - ``heading_path``: the breadcrumb of headings above the chunk.
    - ``chunk_index``: ordinal within the file (drives the deterministic ID).
    """
    post = frontmatter.load(path)
    body = post.content
    if not body.strip():
        return []

    source = _relative_source(path)
    product_id = _infer_product_id(path, dict(post.metadata))

    # File-level metadata that every chunk from this file inherits.
    base_metadata: dict[str, Any] = {"source": source}
    if product_id:
        base_metadata["product_id"] = product_id
        # Carry a display name alongside the id so list_products (and the FE
        # product picker) can label chips without re-reading source files.
        base_metadata["product_name"] = _infer_product_name(path, dict(post.metadata), body)
    # Allowlist of frontmatter fields we promote to chunk metadata. Keep
    # this short — Chroma metadata is searched/filtered, not body text.
    for key in ("name", "status", "owner", "default_url", "health_check", "tags"):
        if key in post.metadata:
            base_metadata[key] = post.metadata[key]

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS_TO_SPLIT_ON,
        strip_headers=False,  # keep headings in the chunk so retrieval sees them
    )
    section_docs = header_splitter.split_text(body)

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_TARGET_CHARS,
        chunk_overlap=CHUNK_OVERLAP_CHARS,
    )

    chunks: list[IndexedChunk] = []
    for section in section_docs:
        # Build a "h1 > h2 > h3" breadcrumb from whatever headers were
        # collected for this section. Use only the levels that actually
        # exist so we don't show an empty trailing arrow.
        heading_path = " > ".join(
            section.metadata[h] for _, h in MARKDOWN_HEADERS_TO_SPLIT_ON if h in section.metadata
        )
        section_meta = {**base_metadata}
        if heading_path:
            section_meta["heading_path"] = heading_path

        for piece in char_splitter.split_text(section.page_content):
            chunk_index = len(chunks)
            chunks.append(
                IndexedChunk(
                    chunk_id=f"{source}::{chunk_index}",
                    text=piece,
                    metadata=_clean_metadata({**section_meta, "chunk_index": chunk_index}),
                )
            )

    return chunks


def _tep_web_relpath(path: Path) -> str:
    """POSIX path of a tep-web source file relative to ``tep_web_root``.

    Used for the chunk id prefix and ``heading_path`` metadata. Resolved
    against ``tep_web_root`` (not ``REPO_ROOT``) because the tep-web corpus
    lives outside the repo — ``_relative_source`` would raise here.
    """
    return path.resolve().relative_to(settings.tep_web_root.resolve()).as_posix()


def _is_tep_web(path: Path) -> bool:
    """True iff ``path`` lives under ``tep_web_root`` (the external corpus)."""
    try:
        path.resolve().relative_to(settings.tep_web_root.resolve())
        return True
    except ValueError:
        return False


def chunk_code_file(path: Path) -> list[IndexedChunk]:
    """Chunk a non-markdown source file (the tep-web code corpus).

    Code has no markdown headings, so we skip ``MarkdownHeaderTextSplitter``
    and split with ``RecursiveCharacterTextSplitter`` only, prefixing each
    chunk with a synthetic header (``// tep-web :: <relpath>``) so the
    embedder sees file context the splitter would otherwise strip.

    Every chunk is tagged ``product_id="acelents"`` so ``list_products`` /
    the FE picker surface it and ``search_documentation`` can scope to it.
    ``heading_path`` carries the relative filepath so citations read like a
    path breadcrumb (``apps/src/pages/index.astro``) instead of an md heading.
    """
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if not body.strip():
        return []

    rel = _tep_web_relpath(path)
    source = f"tep-web::{rel}"
    base_metadata: dict[str, Any] = {
        "source": source,
        "product_id": "acelents",
        "product_name": "Acelents Website",
        "status": "active",
        "heading_path": rel,
        "kind": path.suffix.lstrip("."),
    }

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_TARGET_CHARS,
        chunk_overlap=CHUNK_OVERLAP_CHARS,
    )

    chunks: list[IndexedChunk] = []
    for piece in char_splitter.split_text(f"// tep-web :: {rel}\n{body}"):
        chunk_index = len(chunks)
        chunks.append(
            IndexedChunk(
                chunk_id=f"{source}::{chunk_index}",
                text=piece,
                metadata=_clean_metadata({**base_metadata, "chunk_index": chunk_index}),
            )
        )
    return chunks


def _display_source(path: Path) -> str:
    """Human-readable source label for the indexing log, repo- or tep-web-aware."""
    if _is_tep_web(path):
        return f"tep-web::{_tep_web_relpath(path)}"
    return _relative_source(path)


# ─── Embedding + upsert ──────────────────────────────────────────────────


def _get_collection(client: PersistentClient) -> Collection:
    """Always return the docs collection — created on first run, reused after.

    No ``embedding_function=`` argument is passed because we compute
    embeddings ourselves (see :func:`_embed_texts`). That keeps the choice
    of embedder explicit and visible at the call site rather than hidden in
    Chroma's defaults.
    """
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Run fastembed over a list of strings.

    First call downloads the ONNX model (~50MB) and caches it under
    ``~/.cache/fastembed/`` — the first ``just index`` is therefore slower
    than later runs. No network calls after that.
    """
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    # ``embed`` returns numpy arrays; ChromaDB accepts plain lists. Convert
    # explicitly so the call site doesn't lug numpy types around.
    return [vec.tolist() for vec in model.embed(list(texts))]


def _chunk_id_prefix(path: Path) -> str:
    """The ``source`` half of every chunk ID produced from ``path``.

    Chunk IDs are ``f"{source}::{chunk_index}"`` (see :func:`chunk_file` and
    :func:`chunk_code_file`), so ``f"{_chunk_id_prefix(path)}::"`` matches
    exactly the chunks belonging to one file.
    """
    if _is_tep_web(path):
        return f"tep-web::{_tep_web_relpath(path)}"
    return _relative_source(path)


def _prune_stale_chunks(
    collection: Collection,
    current_ids: set[str],
    protected_prefixes: set[str] | None = None,
) -> int:
    """Remove chunks from the collection whose IDs are no longer produced.

    Without this step, deleting a doc file would leave its chunks stranded
    in the index — they would still be returned by retrieval. Run after
    every upsert so the corpus mirrors what's on disk.

    ``protected_prefixes`` spares the chunks of files that failed to parse on
    this run. Those files produced no chunks, so they would otherwise look
    exactly like deleted files and lose their previously-indexed content —
    meaning a stray colon in one document would silently delete that
    document's answers rather than merely failing to refresh them. Retrieval
    keeps serving the last good version until the file is fixed.

    Returns the number of chunks deleted (for logging).
    """
    protected = tuple(f"{prefix}::" for prefix in (protected_prefixes or set()))
    existing = collection.get(include=[])  # only need IDs
    stale = [
        cid
        for cid in existing.get("ids", [])
        if cid not in current_ids and not (protected and cid.startswith(protected))
    ]
    if stale:
        collection.delete(ids=stale)
    return len(stale)


# ─── Public entry point ──────────────────────────────────────────────────


def build_index() -> None:
    """End-to-end indexing run — what ``just index`` calls.

    Idempotent: running twice on an unchanged corpus produces an unchanged
    index (same IDs, same content). Stale chunks from deleted files are
    pruned at the end.

    Not transactional: a crash midway leaves the collection partially
    updated. Re-running is safe — the upsert will catch up.
    """
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(path=str(settings.chroma_persist_dir))
    collection = _get_collection(client)

    # 1. Discover all source files across every registered corpus.
    sources: list[Path] = []
    for discover in SOURCE_DISCOVERERS:
        sources.extend(discover())

    print(f"[indexing] persist dir: {settings.chroma_persist_dir}")
    print(f"[indexing] source files: {len(sources)}")

    if not sources:
        print("[indexing] no source files found — nothing to do")
        return

    # 2. Chunk every file. We hold all chunks in memory because the corpus
    #    is small (hundreds of files, not millions). If that ever changes,
    #    stream this loop and upsert in batches per file. Files under
    #    tep_web_root (the external Acelents source corpus) go through the
    #    code chunker; everything else through the markdown chunker.
    #
    #    Each file is chunked inside its own try/except. Without that guard a
    #    single unparseable file aborted the entire run: one document whose
    #    YAML frontmatter did not parse (a ``product_name`` containing a colon
    #    is enough) raised out of ``chunk_file`` and took the whole corpus with
    #    it, so every later ``just index`` failed identically until a human
    #    found the offending file by hand. One bad document should cost you
    #    that document, not the index.
    all_chunks: list[IndexedChunk] = []
    skipped: list[tuple[Path, str]] = []
    for path in sources:
        try:
            file_chunks = chunk_code_file(path) if _is_tep_web(path) else chunk_file(path)
        except Exception as exc:  # noqa: BLE001 — any parse failure is per-file news
            skipped.append((path, f"{type(exc).__name__}: {exc}"))
            print(f"[indexing] SKIPPED {_display_source(path)} — {type(exc).__name__}: {exc}")
            continue
        all_chunks.extend(file_chunks)
        print(f"[indexing] {_display_source(path)} -> {len(file_chunks)} chunk(s)")

    if not all_chunks:
        print("[indexing] discovered files but every one was empty — nothing to upsert")
        return

    print(f"[indexing] total chunks: {len(all_chunks)}")
    print(f"[indexing] embedding with {EMBEDDING_MODEL_NAME} (first run downloads model)...")

    # 3. Embed. Done in one batch so fastembed can parallelise internally.
    embeddings = _embed_texts(chunk.text for chunk in all_chunks)

    # 4. Upsert into Chroma. Deterministic IDs make this idempotent.
    collection.upsert(
        ids=[chunk.chunk_id for chunk in all_chunks],
        documents=[chunk.text for chunk in all_chunks],
        metadatas=[chunk.metadata for chunk in all_chunks],
        embeddings=embeddings,
    )

    # 5. Drop chunks from files that no longer exist or were renamed — but not
    #    those of files that merely failed to parse this run (see docstring).
    stale_removed = _prune_stale_chunks(
        collection,
        current_ids={chunk.chunk_id for chunk in all_chunks},
        protected_prefixes={_chunk_id_prefix(path) for path, _ in skipped},
    )
    if stale_removed:
        print(f"[indexing] pruned {stale_removed} stale chunk(s) from deleted/renamed files")

    print(f"[indexing] done — collection '{COLLECTION_NAME}' now has {collection.count()} chunk(s)")

    # Loud, and last, so a skipped file cannot scroll past unnoticed in CI logs
    # or in the output of a `just index` triggered from the web form.
    if skipped:
        print(f"[indexing] WARNING: {len(skipped)} file(s) skipped — fix these and reindex:")
        for path, reason in skipped:
            print(f"[indexing]   - {_display_source(path)}: {reason}")


if __name__ == "__main__":
    # Entry point for ``just index`` (which runs ``python -m agent.indexing``).
    # Keep this block tiny — orchestration of the index lives in build_index().
    build_index()
