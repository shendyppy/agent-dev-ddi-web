# docs/products/ — AGENTS.md

This folder holds **per-product documentation** consumed by the RAG indexer. Each subfolder = one product.

**Before editing**, read [`../PRODUCT-DOC-FORMAT.md`](../PRODUCT-DOC-FORMAT.md). The format is strict on purpose — the agent's prompts and the indexer both assume the exact structure.

## Quick rules

1. **Folder name = `id` in frontmatter.** kebab-case. Stable identifier — never rename.
2. **Copy `_template/` to start a new product.** Don't write from scratch.
3. **Heading names are exact.** "How to run", not "Running" or "Getting started".
4. **Bump `last_reviewed`** after re-verifying. Stale docs cause hallucinations.
5. **Update [`../product-catalog.md`](../product-catalog.md)** when adding/removing a product (the index file).
6. **Run `just index`** after any change to rebuild ChromaDB.

## When to split features into separate files

Always, if a feature needs > 5 lines to document. Otherwise inline under `## Features` in `product.md` is fine.

## What the indexer does with this folder

Walks every `**/*.md`, parses frontmatter, splits body by headings, embeds chunks, stores in ChromaDB with metadata `{product_id, feature_id?, source_path, heading_path}`. The agent can filter on metadata to scope retrieval (e.g., "only chunks where `product_id=example-product`").

## See also

- [`../PRODUCT-DOC-FORMAT.md`](../PRODUCT-DOC-FORMAT.md) — the format spec
- [`../adr/0006-product-doc-format.md`](../adr/0006-product-doc-format.md) — why this format
- [`../../apps/backend/src/agent/indexing.py`](../../apps/backend/src/agent/indexing.py) — the consumer
