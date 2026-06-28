# ADR 0007 — Retire `portrai_cms_agent.py`, finalize the MCP/LangGraph/Chroma path

- **Status**: Accepted
- **Date**: 2026-06-26
- **Supersedes**: nothing (clarifies how earlier ADRs apply when a "quick path" exists in parallel)

## Context

Two implementations of the chatbot grew side-by-side in `apps/backend/`:

1. **Path A — the documented architecture.** Defined across ADR 0002 (MCP skills), ADR 0003 (LiteLLM gateway), and ADR 0004 (Chroma + fastembed). Skeletal code under `agent/graph.py`, `agent/mcp_clients.py`, `agent/indexing.py`, and `mcp_servers/*/`. Mostly stubs and `TODO` markers at the time of writing.
2. **Path B — `apps/backend/src/agent/portrai_cms_agent.py`.** A working class that talks to Google GenAI directly, holds the system prompt as a Python string literal, reads `.env` by hand, and does in-memory cosine similarity over markdown files. Wired to the frontend via `POST /api/portrai-cms-agent`. Currently the only path the chat UI uses.

The frontend (`Chat.tsx`) calls only Path B. Path A's `POST /api/chat` SSE endpoint is wired but unused.

Path B violates four core invariants from `AGENTS.md`:

| Rule | Where Path B breaks it |
|---|---|
| Prompts as code (lives in `prompts/`) | `portrai_cms_agent.py:50-60` — `system_instruction` is an inline Python string |
| Single LLM gateway through `agent.llm` | `portrai_cms_agent.py` imports `google.genai` directly; no LiteLLM, no Langfuse trace |
| Settings via `agent.settings` | `portrai_cms_agent.py:68-80` reads `os.environ` and parses `.env` manually |
| Skills as MCP servers | The whole RAG flow is one inline class — no MCP server, no `skill.md`, no tool spec |

Path B also has no eval coverage and no `Sources:` citation in its responses, so the "Eval-gated agent changes" rule cannot apply to it.

Teammates new to the codebase have asked which path to follow. Maintaining both is teaching the wrong pattern.

## Decision

**Retire Path B.** All chatbot traffic flows through Path A:

1. `Chat.tsx` calls `POST /api/chat` (SSE) instead of `/api/portrai-cms-agent`.
2. `portrai_cms_agent.py` is deleted along with the `/api/portrai-cms-agent` endpoint registration in `server.py`.
3. The system prompt currently inlined in `portrai_cms_agent.py` moves to `prompts/system/portrai-cms.md` (or merges into `prompts/system/main-agent.md` if its instructions generalise).
4. The existing knowledge corpus under `docs/knowledge-base/*.md` is kept and added as an indexing source so that PortrAI CMS users do not lose answers during the cutover.
5. The dependencies `google-genai` and `numpy` are removed from `apps/backend/pyproject.toml` — fastembed and Chroma cover the embedding/similarity job.

In the same set of changes, the stubs along Path A are filled in (real `indexing.py`, real `mcp_clients.discover_all_tools()` + tool dispatch, real `search_docs.handle()`, real `evals/run.py`).

## Alternatives considered

| Option | Verdict |
|---|---|
| **A. Retire Path B (this ADR)** | Chosen — restores a single canonical pattern and matches every ADR already accepted. |
| **B. In-place fix Path B** (move prompt to `prompts/`, route via `agent.llm`, keep it as a separate "PortrAI mode") | Rejected — still leaves two parallel orchestrators. Teammates would copy the easier path and the MCP work would never get finished. |
| **C. Hybrid — Path B for PortrAI, Path A for future products** | Rejected — same problem as B, doubled. Two prompts, two retrieval implementations, two ways to debug, two places to instrument observability. |

## Consequences

**Positive**

- Single orchestrator. The code matches the architecture diagram in `docs/architecture.md` and the rules in `AGENTS.md`.
- Every LLM call is traced (Langfuse) and every retrieval is testable in isolation (`just mcp-inspect search_docs`).
- New product onboarding is one shape: drop docs under `docs/products/<id>/`, run `just index`, add an eval case.
- Provider swap is one env var (`LITELLM_MODEL=…`). PortrAI's Gemini lock-in is gone.

**Negative**

- A short cutover window where the chat UI may be less polished than the existing Path B response style. Mitigated by porting the prompt verbatim before deletion.
- The knowledge corpus under `docs/knowledge-base/` was authored as free-form context, not following `PRODUCT-DOC-FORMAT.md`. It will be indexed as-is for continuity; reshaping to the product-format is tracked as follow-up, not a blocker.
- One-time migration cost: rewrite the chat island to consume SSE.

## Migration checklist (this PR / set of commits)

- [ ] Real `agent/indexing.py` (chunk + fastembed + Chroma upsert; includes `docs/knowledge-base/` as a source).
- [ ] Real `agent/mcp_clients.py` discovery + connection pool.
- [ ] Real `agent/graph.py call_tools` dispatching to the right MCP server.
- [ ] Real `mcp_servers/search_docs/handler.py` (Chroma query path).
- [ ] `Chat.tsx` rewritten to SSE-consume `/api/chat`.
- [ ] `portrai_cms_agent.py` deleted; `/api/portrai-cms-agent` endpoint deleted.
- [ ] `prompts/system/portrai-cms.md` (or merged) created from the retired inline string.
- [ ] `pyproject.toml`: `google-genai` and `numpy` removed.
- [ ] `evals/run.py` implemented so the above can be gated.

## See also

- [ADR 0002 — Skills as MCP servers](0002-mcp-skills-architecture.md)
- [ADR 0003 — LLM via LiteLLM](0003-llm-via-litellm.md)
- [ADR 0004 — RAG stack: ChromaDB + fastembed](0004-rag-stack.md)
- [ADR 0006 — Per-product documentation format](0006-product-doc-format.md)
- [AGENTS.md](../../AGENTS.md) — invariants this restores
