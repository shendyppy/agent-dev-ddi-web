# ADR 0006 — Per-product documentation format

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

The agent's value depends entirely on the quality of retrieval over our product documentation. We need a documentation format that:

1. **Chunks cleanly** under recursive character splitting (no orphaned context).
2. **Lets the LLM extract specific fields** reliably (run command, default URL, feature list).
3. **Supports filtering at retrieval time** (only chunks for product X, only active products).
4. **Is human-maintainable** without a CMS or special tooling.
5. **Can be validated** mechanically so docs don't rot silently.

Without a strict format, we'll get inconsistent docs ("Getting Started" vs "How to run" vs "Setup"), which forces the LLM to do heavy work matching headings, and produces worse answers.

## Decision

Standardize the per-product doc format as specified in [`docs/PRODUCT-DOC-FORMAT.md`](../PRODUCT-DOC-FORMAT.md). Key choices:

| Choice | Reason |
|---|---|
| **One folder per product** under `docs/products/<product-id>/` | Scopes retrieval (metadata `product_id`); supports `features/` subfolder |
| **YAML frontmatter** on `product.md` + every `feature.md` | Machine-readable metadata for filtering, citing, validation |
| **Exact section headings** (`## Overview`, `## How to run`, etc.) | Prompts reference these; chunks inherit heading-path metadata; consistency = better retrieval |
| **One feature per file** when feature needs > 5 lines | Each feature becomes one retrievable unit; no cross-feature chunk collisions |
| **Separate `docs/product-catalog.md` as an index** | Short index doc is itself indexable (cheap broad queries); detail lives in per-product folders |
| **Stable kebab-case IDs** matching folder names | Stable references across docs, screenshot scenarios, eval cases |

## Alternatives considered

| Option | Rejected because |
|---|---|
| One big `docs.md` per product | Single chunk wins all retrievals for that product → no granular feature lookup |
| Free-form markdown (no required structure) | Inconsistency tanks retrieval; LLM has to do too much heuristic work |
| JSON/YAML-only (no markdown body) | Loses the natural-language detail the LLM needs to synthesize answers |
| External CMS (Notion, Confluence) | Adds an external dependency; harder to version with code; auth complexity |
| Auto-extract from product READMEs | Quality varies wildly across products; no enforcement of completeness |

## Consequences

**Positive:**
- Predictable RAG behavior — same kind of question always hits the same section.
- Cheap validation: a linter can check structure mechanically.
- Documenting a new product is a copy-paste from `_template/` — low friction.
- Frontmatter metadata enables: filtered retrieval, status-based exclusion (deprecated products), citation rendering, health-check skill wiring.

**Negative:**
- Stricter than free-form — contributors must learn the format. Mitigated by `_template/` and the linter.
- Format changes are migrations — bumping the spec requires updating every existing doc. Mitigated by versioning the spec in this ADR and making changes additive when possible.

## See also

- [`docs/PRODUCT-DOC-FORMAT.md`](../PRODUCT-DOC-FORMAT.md) — the spec
- [`docs/products/_template/`](../products/_template/) — copy-paste template
- [ADR 0004 — RAG stack](0004-rag-stack.md) — why ChromaDB + fastembed, which the chunking strategy is tuned for
