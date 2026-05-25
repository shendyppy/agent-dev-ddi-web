"""RAG retrieval over ChromaDB.

Skeleton — wire up to chromadb.PersistentClient when ready.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

CHROMA_DIR = Path(os.environ.get("CHROMA_PERSIST_DIR", ".data/chroma"))


class SearchInput(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class Chunk(BaseModel):
    text: str
    source: str
    score: float


class SearchOutput(BaseModel):
    chunks: list[Chunk]
    warning: str | None = None


async def handle(payload: SearchInput) -> SearchOutput:
    # TODO: real implementation
    #   client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    #   collection = client.get_or_create_collection("docs", embedding_function=fastembed_fn)
    #   results = collection.query(query_texts=[payload.query], n_results=payload.top_k)
    #   build Chunks from results
    if not CHROMA_DIR.exists():
        return SearchOutput(
            chunks=[],
            warning="index not built — run `just index`",
        )
    return SearchOutput(
        chunks=[
            Chunk(
                text=f"[stub] would return top {payload.top_k} chunks for: {payload.query!r}",
                source="docs/product-catalog.md",
                score=0.5,
            )
        ],
    )
