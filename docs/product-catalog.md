# Product catalog (index)

Short index of every product the documentation agent can answer about. Detail lives in [`products/<product-id>/`](products/) — one folder per product.

> **Adding a product?** Don't just edit this file. The full flow is in [`PRODUCT-DOC-FORMAT.md`](PRODUCT-DOC-FORMAT.md). Steps:
> 1. Copy `products/_template/` → `products/<your-product-id>/`.
> 2. Fill in `product.md` + at least one `features/<feature>.md`.
> 3. Add a row to the table below.
> 4. Run `just index`.

---

## Index

| ID | Name | Status | Owner | Default URL | Docs |
|---|---|---|---|---|---|
| `_template` | (template — not a real product) | — | — | — | [products/_template/](products/_template/) |
<!-- Insert new rows here as products are added. Example:
| `example-product` | Example Product | active | team-foo | http://localhost:3000 | [products/example-product/](products/example-product/) |
-->

---

## What this file is for

This is an **index**, not a detail page. It exists so the chatbot can answer broad questions cheaply ("what products do we have?") without retrieving every per-product chunk.

- Short rows = small chunks = quick retrieval.
- The `list_products` MCP skill parses this table directly (no LLM call needed for the simple "list everything" path).
- The full per-product docs in `products/` get indexed separately into ChromaDB for semantic search.

If you find yourself wanting to write paragraphs of detail here, that's a signal it belongs in the per-product `product.md` instead.
