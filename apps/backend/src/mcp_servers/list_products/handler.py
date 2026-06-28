"""Lists the products the agent can answer about.

Source of truth is the ChromaDB index built by ``agent.indexing``: we read the
distinct ``product_id`` / ``product_name`` metadata off the indexed chunks. That
guarantees the catalogue the UI shows is exactly what retrieval can filter on —
add a doc under ``docs/knowledge-base/`` (or ``docs/products/``), run
``just index``, and the product appears here automatically. No second list to
keep in sync.
"""

from __future__ import annotations

import os
from pathlib import Path

from chromadb import PersistentClient
from pydantic import BaseModel

# Mirror search_docs/handler.py — MCP servers must not import agent modules,
# so we read the same env var with the same default.
CHROMA_PERSIST_DIR = Path(
    os.environ.get("CHROMA_PERSIST_DIR", str(Path.cwd() / ".data" / "chroma"))
)
COLLECTION_NAME = "docs"


class Product(BaseModel):
    id: str
    name: str
    status: str = "active"
    doc_count: int = 0  # number of indexed chunks tagged with this product


class ListProductsOutput(BaseModel):
    products: list[Product]


def _collect_products() -> list[Product]:
    """Scan indexed chunk metadata and fold it into one row per product_id."""
    if not CHROMA_PERSIST_DIR.exists():
        return []

    client = PersistentClient(path=str(CHROMA_PERSIST_DIR))
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        # No collection yet → behave like "no products" rather than erroring.
        return []

    got = collection.get(include=["metadatas"])
    products: dict[str, Product] = {}
    for meta in got.get("metadatas", []) or []:
        meta = meta or {}
        product_id = meta.get("product_id")
        if not isinstance(product_id, str) or not product_id:
            continue  # catalog/architecture chunks carry no product scope
        existing = products.get(product_id)
        if existing is None:
            products[product_id] = Product(
                id=product_id,
                name=str(meta.get("product_name") or product_id),
                status=str(meta.get("status") or "active"),
                doc_count=1,
            )
        else:
            existing.doc_count += 1

    return sorted(products.values(), key=lambda p: p.name.lower())


async def handle() -> ListProductsOutput:
    return ListProductsOutput(products=_collect_products())
