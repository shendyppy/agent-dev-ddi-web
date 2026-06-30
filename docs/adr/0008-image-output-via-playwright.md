# ADR 0008 — Image output via Playwright + external source ingestion

- **Status**: Accepted
- **Date**: 2026-06-29
- **Supersedes**: nothing (fills in the `capture_screenshot` stub left by ADR 0002/0007)

## Context

The agent answered only in text. Two adjacent asks landed together:

1. **Show images in answers.** When a user asks "what does the tour page look
   like?" the agent should display a live screenshot of
   `https://dev.acelents.com/...` inline in the chat, not describe it in prose.
2. **Code-related knowledge base from the tep-web repo.** The agent should
   answer code-level questions about the Acelents site (routes, components,
   tech stack) from the actual source under `C:\Project\DDI\Acelents\tep-web`.

The repo was already half-scaffolded for (1): the `capture_screenshot` MCP
skill existed but its handler was a stub; a `just screenshot <scenario>` recipe
existed; the main-agent prompt already told the model to use screenshots
proactively; `packages/e2e/` had Playwright configured (with zero tests); and
the frontend markdown renderer (`marked` + `DOMPurify`) already permits `<img>`,
so a markdown `![](url)` renders with **no frontend change**. The open question
was how an image should travel from the skill to the user, and how to ingest a
non-markdown source corpus that lives outside the repo.

## Decision

**Screenshots travel as a markdown image URL inside the assistant's text
answer — not as a new transport type and not as MCP image content parts.**

1. The `capture_screenshot` skill captures a PNG via Playwright, writes it under
   `settings.screenshot_dir`, and returns an absolute `/screenshots` URL.
   FastAPI serves that dir through a `StaticFiles` mount. The agent embeds the
   URL as `![alt](url)`; the existing SSE `message` event carries it as text;
   the FE `renderMarkdown()` turns it into `<img>`. **No change to `graph.py`,
   `mcp_clients.py`, the SSE contract, or the frontend.**
2. The skill accepts **`scenario` OR `url`** (canonical pages vs any live
   route). Both paths go through Playwright in `packages/e2e` (chromium-only)
   via `just screenshot` / `just screenshot-url`; on-demand `url` captures are
   cached per URL.
3. The tep-web source is ingested by a new **code-aware** discoverer +
   `chunk_code_file` in `indexing.py`. It is external to `REPO_ROOT`, so it
   gets its own chunk-id scheme (`tep-web::<relpath>`) and skips the
   markdown-only `MarkdownHeaderTextSplitter`. Every chunk is tagged
   `product_id="acelents"`, so `list_products` / the FE picker surface it
   automatically. A thin curated `docs/products/acelents/product.md` (per ADR
   0006) sits alongside it to power the catalog, health check, and run
   instructions.

## Alternatives considered

| Option | Verdict |
|---|---|
| **A. Markdown image URL in text (this ADR)** | Chosen — reuses the existing text + markdown path; zero transport/graph/FE changes; model-agnostic. |
| **B. New SSE `image` event + structured content blocks** | Rejected — forces coordinated changes in `graph.py`, `server.py`, `use-chat.ts`, and `MessageList`; SSE drift is the most common bug here; buys nothing the markdown path doesn't already give. |
| **C. Skill returns MCP image content parts** | Rejected — `mcp_clients.call_tool` currently stringifies non-text parts; supporting image parts means bridge work across the MCP→LangGraph→SSE path, and the model still has to place the image in its answer text. A URL is simpler. |
| **D. Pre-crawl the site into a static gallery** | Rejected — less flexible than on-demand `url` capture; the live capture is cheap and cached, and a gallery drifts from the real site. |
| **E. Curated-only KB (hand-written `.md`)** | Rejected — does not satisfy the "code-related from the repo" ask; raw source answers deeper code questions. |
| **F. Raw-source-only KB (no `product.md`)** | Rejected — loses the catalog/picker/health/run scaffolding that ADR 0006's product format provides. A (Duo) is both. |

## Consequences

**Positive**

- Minimal blast radius: the image feature touches one skill, one static mount,
  and one prompt rule — the orchestrator, transport, and UI are untouched.
- Deterministic captures (single chromium project, fixed viewport) and a
  per-scenario/per-URL cache keep repeat calls cheap.
- The agent is driver-flexible: canonical pages via `scenario`, anything else
  via `url`.
- Code questions about Acelents are answerable from real source, and the
  product picker picks the product up with no extra wiring.

**Negative**

- `https://dev.acelents.com` must be reachable from the agent host at capture
  time — a network dependency on a tool call. If the site needs auth, the
  Playwright scripts need an auth step (not done here).
- Chromium must be installed (`just install-e2e`). First capture pays browser
  startup.
- Full-page captures of a JS-hydrated site can catch transient states;
  mitigated by `waitUntil: 'networkidle'` in the scenarios.
- `tep_web_root` is a host-specific absolute path; exposed as `TEP_WEB_ROOT`
  for portability.
- The `.env` file is **not** propagated to the MCP subprocess (pydantic-settings
  does not export to `os.environ`), so `SCREENSHOT_DIR` / `SCREENSHOT_BASE_URL`
  overrides must be real OS env vars — documented in `.env.example` to avoid a
  silent serve/write mismatch.

## See also

- [ADR 0002 — Skills as MCP servers](0002-mcp-skills-architecture.md)
- [ADR 0004 — RAG stack: ChromaDB + fastembed](0004-rag-stack.md)
- [ADR 0006 — Per-product documentation format](0006-product-doc-format.md)
- [ADR 0007 — Retire `portrai_cms_agent.py`](0007-retire-portrai-cms-agent.md)
