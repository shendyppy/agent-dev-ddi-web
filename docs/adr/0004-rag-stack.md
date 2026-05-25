# ADR 0004 — RAG stack: ChromaDB + fastembed

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

The agent's core skill is retrieving relevant doc chunks. We need:

- A vector store that persists between restarts.
- An embedding model that doesn't add API cost or another secret to manage.
- Both must run on a single small VPS for MVP.

## Decision

- **Vector store**: **ChromaDB** in persistent (file-backed) mode. Index lives under `.data/chroma/`.
- **Embeddings**: **fastembed** (BAAI/bge-small-en-v1.5 default) — runs locally, CPU-fast, no API key.
- **Chunking**: recursive character splitter, 800 tokens with 100 token overlap. Tunable in `apps/backend/src/agent/indexing.py`.
- **Reindex trigger**: manual via `just index`. CI rebuilds on changes to `docs/` and product source paths.

## Why these picks

| Option | Why this one |
|---|---|
| ChromaDB vs Qdrant | Qdrant needs a separate container; ChromaDB embeds in-process. Switch if corpus > ~500k chunks. |
| ChromaDB vs FAISS | FAISS is in-memory; we want persistence without managing snapshot files manually. |
| fastembed vs Voyage/OpenAI | No API key, no cost, no rate limit. Quality is "good enough" for technical docs; upgrade path documented. |
| fastembed vs sentence-transformers | fastembed wraps optimized ONNX models — faster CPU inference, smaller install footprint. |

## Upgrade path

If retrieval quality plateaus:

1. Swap fastembed → Voyage `voyage-3` (set `VOYAGE_API_KEY`, change `EMBEDDING_PROVIDER` env var).
2. Add a reranker (Cohere rerank or `bge-reranker-base` via fastembed) — currently scaffolded but not enabled.
3. Switch ChromaDB → Qdrant if we need multi-tenant or distributed.

Each upgrade is a localized change in `indexing.py` + one env var.

## Consequences

**Positive:**
- Zero external dependencies for retrieval. `just bootstrap` + `just index` and you have a working RAG.
- No surprise embedding bills.
- Local-first dev — no internet needed for retrieval.

**Negative:**
- fastembed quality < Voyage/OpenAI embeddings on subtle semantic queries. Mitigated by chunking strategy and reranker upgrade path.
- ChromaDB single-writer — fine for our scale, would block multi-instance backend if we scale horizontally.

## See also

- ChromaDB: https://docs.trychroma.com
- fastembed: https://github.com/qdrant/fastembed
- [ADR 0002 — MCP skills](0002-mcp-skills-architecture.md) — `search_docs` is the skill that uses this stack
