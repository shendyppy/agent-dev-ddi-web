# Architecture

High-level system view of the Documentation Agent Bot.

## System diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         User (browser)                             │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ HTTPS
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  Astro Frontend (Cloudflare Pages)                                 │
│  - Static pages (product catalog browsing, deep links)             │
│  - Preact island: <Chat /> component (SSE streaming)               │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ POST /chat (SSE)
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  FastAPI Orchestrator  (Fly.io / Docker Compose)                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  LangGraph state machine                                     │  │
│  │   ┌──────┐    ┌──────────┐    ┌─────────────┐               │  │
│  │   │ plan │ -> │ call LLM │ -> │ tool router │               │  │
│  │   └──────┘    └──────────┘    └─────┬───────┘               │  │
│  │                       ▲             │                        │  │
│  │                       └─────────────┘ (loop)                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │ LLM via LiteLLM            │ Tools via MCP client          │
│       ▼                             ▼                              │
│  ┌──────────┐         ┌─────────────────────────────────────┐     │
│  │ LiteLLM  │         │  MCP Client (stdio or SSE)          │     │
│  │ Anthropic│         └──────┬──────┬──────┬──────┬─────────┘     │
│  │ OpenAI   │                │      │      │      │               │
│  │ Ollama   │                ▼      ▼      ▼      ▼               │
│  └────┬─────┘          ┌─────────────────────────────────────┐    │
│       │                │  MCP Servers (one per skill)        │    │
│       │                │  search_docs   capture_screenshot   │    │
│       │                │  list_products check_app_health     │    │
│       │                │  get_run_instructions, ...          │    │
│       │                └──────┬──────────────────┬───────────┘    │
│       │                       │                  │                 │
│       │                       ▼                  ▼                 │
│       │                ┌────────────┐    ┌──────────────┐         │
│       │                │ ChromaDB   │    │ Playwright   │         │
│       │                │ (file)     │    │ (e2e pkg)    │         │
│       │                └────────────┘    └──────────────┘         │
│       │                                                            │
│       ▼                                                            │
│  ┌──────────────┐                                                 │
│  │  Langfuse    │ ← every LLM call traced                         │
│  │  (self-host) │                                                 │
│  └──────────────┘                                                 │
└────────────────────────────────────────────────────────────────────┘
```

## Request flow: "How do I run product XYZ?"

1. User types question in chat UI (Preact island).
2. Browser opens SSE stream to `POST /chat`.
3. FastAPI hands the message to the LangGraph state machine.
4. Graph node `call_llm` invokes LiteLLM → Claude Sonnet 4.6.
5. LLM decides to call tool `search_documentation(query="run product XYZ")`.
6. Orchestrator's MCP client routes the call to the `search_docs` MCP server.
7. MCP server:
   - Embeds query with fastembed.
   - Queries ChromaDB → top-5 chunks.
   - Returns chunks + source citations.
8. LLM receives chunks, synthesizes the answer, streams tokens back.
9. Frontend renders tokens as they arrive.
10. Every step is traced to Langfuse with session_id.

## Why these choices

Each non-trivial decision has an ADR. Start with:

- [`adr/0001-monorepo-layout.md`](adr/0001-monorepo-layout.md) — why monorepo, why this folder shape
- [`adr/0002-mcp-skills-architecture.md`](adr/0002-mcp-skills-architecture.md) — why MCP instead of inline tools
- [`adr/0003-llm-via-litellm.md`](adr/0003-llm-via-litellm.md) — why LiteLLM, default Claude
- [`adr/0004-rag-stack.md`](adr/0004-rag-stack.md) — why ChromaDB + fastembed
- [`adr/0005-deployment-strategy.md`](adr/0005-deployment-strategy.md) — why not EC2, why Fly.io / Cloudflare

## Non-goals (for now)

- Multi-tenant / per-user data isolation
- User auth (chatbot is internal/anonymous for v1)
- Real-time doc indexing (batch reindex via `just index` is fine)
- Fine-tuning the LLM (RAG-only)
- Mobile-first UI (desktop-first is OK)
