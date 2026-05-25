"""ChromaDB indexer.

Run via `just index`. Walks configured source paths, parses frontmatter,
chunks by heading + recursive character split, embeds with fastembed,
persists to `.data/chroma/`.

Sources:
- docs/products/**/*.md        ← per-product docs (the bulk of the corpus)
- docs/product-catalog.md       ← short index, indexed too for broad queries
- docs/architecture.md          ← so the agent can answer about itself

Per ADR 0004: ChromaDB + fastembed. Per ADR 0006: product docs follow a
strict format with frontmatter — the indexer reads frontmatter into chunk
metadata for filtered retrieval (e.g. `product_id=foo`).
"""

from __future__ import annotations

from pathlib import Path

from .settings import REPO_ROOT, settings

DOCS_ROOT = REPO_ROOT / "docs"
PRODUCTS_DIR = DOCS_ROOT / "products"

# Top-level files indexed in addition to per-product docs.
TOP_LEVEL_SOURCES: list[Path] = [
    DOCS_ROOT / "product-catalog.md",
    DOCS_ROOT / "architecture.md",
]


def discover_product_docs() -> list[Path]:
    """Return every .md under docs/products/, skipping the _template folder."""
    if not PRODUCTS_DIR.exists():
        return []
    return [
        p
        for p in PRODUCTS_DIR.rglob("*.md")
        if "_template" not in p.parts
    ]


def build_index() -> None:
    """Build (or rebuild) the ChromaDB index from configured sources."""
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)

    product_docs = discover_product_docs()
    all_sources = TOP_LEVEL_SOURCES + product_docs

    print(f"[indexing] persist dir: {settings.chroma_persist_dir}")
    print(f"[indexing] top-level sources: {len(TOP_LEVEL_SOURCES)}")
    print(f"[indexing] product doc files: {len(product_docs)}")
    print(f"[indexing] total files: {len(all_sources)}")

    # TODO:
    #  1. For each file: read content, parse frontmatter (python-frontmatter)
    #  2. Split body by markdown headings, then by recursive character splitter (800 / 100)
    #  3. Attach metadata to each chunk: {source, product_id, feature_id, heading_path, status}
    #  4. Embed with fastembed (BAAI/bge-small-en-v1.5)
    #  5. Upsert into chromadb.PersistentClient(path=settings.chroma_persist_dir)
    print("[indexing] implementation pending — scaffold only")


if __name__ == "__main__":
    build_index()
