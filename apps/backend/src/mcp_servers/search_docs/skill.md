---
name: search_documentation
version: 1
inputs:
  query: "string — natural-language search query"
  top_k: "integer (default 5) — number of chunks to return"
  product_id: "string (optional) — restrict results to one product's docs; omit to search all"
outputs:
  chunks:
    - text: "string — the chunk content"
      source: "string — source file path or URL"
      score: "float — similarity score (0..1)"
when_to_use: |
  Call this FIRST for any user question about a product, a feature, how to run
  something, or anything that might be in our documentation. Even if you think
  you know the answer, retrieve evidence — answers without retrieval are
  forbidden.
examples:
  - input: { query: "how to run example product", top_k: 3 }
    output:
      chunks:
        - text: "Run with `pnpm dev` on port 3000..."
          source: "docs/product-catalog.md"
          score: 0.87
---

# search_documentation

Semantic search over the ChromaDB index (built by `just index` from sources
listed in `agent/indexing.py`).

**Implementation notes:**
- Query is embedded with fastembed (BAAI/bge-small-en-v1.5).
- ChromaDB returns nearest neighbors by cosine distance.
- Score is `1 - distance`, clipped to [0, 1].
- Optionally rewrites the query first (see `prompts/tools/search-docs.md`) —
  toggle with `QUERY_REWRITE` env var; defaults to off.

**Failure modes to handle:**
- Empty index → return `{"chunks": [], "warning": "index empty, run `just index`"}`.
- All scores below 0.3 → still return chunks but include `warning: "low confidence"`.
