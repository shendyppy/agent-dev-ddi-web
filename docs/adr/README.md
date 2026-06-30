# Architecture Decision Records

Each ADR captures a non-trivial architectural choice with the **Context**, **Decision**, and **Consequences**. Numbered chronologically; never deleted (status changes to `Superseded` instead).

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-monorepo-layout.md) | Monorepo layout | Accepted |
| [0002](0002-mcp-skills-architecture.md) | Skills as MCP servers | Accepted |
| [0003](0003-llm-via-litellm.md) | LLM access via LiteLLM, default Claude Sonnet 4.6 | Accepted |
| [0004](0004-rag-stack.md) | RAG stack: ChromaDB + fastembed | Accepted |
| [0005](0005-deployment-strategy.md) | Deployment: Cloudflare Pages + Fly.io / Docker Compose | Accepted |
| [0006](0006-product-doc-format.md) | Per-product documentation format | Accepted |
| [0007](0007-retire-portrai-cms-agent.md) | Retire `portrai_cms_agent.py`, finalize MCP/LangGraph/Chroma path | Accepted |
| [0008](0008-image-output-via-playwright.md) | Image output via Playwright + external source ingestion | Accepted |

## Writing a new ADR

1. Copy the format from an existing ADR (e.g. 0001).
2. Number = highest existing + 1.
3. Sections: **Context**, **Decision**, **Alternatives considered** (table), **Consequences** (positive/negative), **See also**.
4. Keep it short — one screen if possible. Link to detail, don't inline it.
5. Update this README's index.

## When to write one

Write an ADR when you make a choice that:

- Adds, removes, or replaces a framework/service/library at the architectural level.
- Defines a convention that future code must follow.
- Future-you would say "wait, why did we do it this way?".

Do **not** write an ADR for: routine code changes, bug fixes, refactors that don't change the public shape, prompt iterations.
