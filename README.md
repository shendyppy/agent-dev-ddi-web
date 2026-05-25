# Documentation Agent Bot

A chatbot agent that helps teammates discover **product documentation**, **how to run apps**, and **how to access features** across our portfolio — plus auto-capture UI evidence via Playwright when asked.

Built **AI-first**: prompts are versioned artifacts, every change is gated by an eval suite, every skill is an MCP server (portable to Claude Desktop / Cursor / any MCP client), and the codebase is structured so AI coding agents can pick up work without ramp-up.

---

## Quick links

| If you are... | Read this |
|---|---|
| A human dev, first time here | This file, then [`docs/architecture.md`](docs/architecture.md) |
| An AI coding agent (Claude Code, Cursor, etc.) | [`AGENTS.md`](AGENTS.md) — repo conventions |
| Looking for *why* we picked X | [`docs/adr/`](docs/adr/) — Architecture Decision Records |
| Adding a new skill to the chatbot | [`apps/backend/src/mcp_servers/AGENTS.md`](apps/backend/src/mcp_servers/AGENTS.md) |
| Writing/changing prompts | [`prompts/AGENTS.md`](prompts/AGENTS.md) + [`evals/README.md`](evals/README.md) |
| Documenting a new product | [`docs/PRODUCT-DOC-FORMAT.md`](docs/PRODUCT-DOC-FORMAT.md) |

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Astro** + Preact island for chat | Static-first, ship tiny JS; chat island isolates state |
| Backend orchestrator | **FastAPI** + **LangGraph** | Explicit, testable agent graph (not opaque `AgentExecutor`) |
| LLM provider | **LiteLLM** wrapper, default `claude-sonnet-4-6` | Swap providers via env var; no vendor lock-in |
| Skills | **MCP servers** (one per skill) | Portable — reusable from Claude Desktop / Cursor / our agent |
| Vector store | **ChromaDB** (file-backed) | Zero-ops, persists to disk, no extra service |
| Embeddings | **fastembed** (local) | No API key, no cost, runs CPU-fast |
| Browser automation | **Playwright** | Evidence capture + smoke tests |
| Observability | **Langfuse** (self-hosted) | Trace every LLM call — non-negotiable for RAG |
| Build runner | **just** (justfile) | Cross-platform, Windows-friendly |
| Python deps | **uv** | 10–100x faster than pip, proper lockfile |
| JS deps | **pnpm** | Workspace-aware, disk-efficient |
| Deploy (BE) | **Docker Compose** self-host *or* **Fly.io** | Avoid EC2 cost trap |
| Deploy (FE) | **Cloudflare Pages** | Free, edge CDN, git-driven |

See [`docs/adr/`](docs/adr/) for the reasoning behind each pick.

---

## Prerequisites

Install once on your machine:

```powershell
# Build runner
scoop install just                # or: winget install Casey.Just

# Python toolchain
winget install --id=astral-sh.uv  # or: pipx install uv

# Node toolchain
winget install OpenJS.NodeJS.LTS  # Node 22+
npm install -g pnpm

# Optional but recommended
scoop install gh                  # GitHub CLI
```

Then:

```powershell
just bootstrap   # installs all deps across the monorepo
just dev         # starts FE + BE + MCP servers concurrently
```

That's it. Open http://localhost:4321.

---

## Repo layout

```
agent-fe-ddi-web/
├── README.md                    ← you are here
├── AGENTS.md                    ← conventions for AI coding agents
├── CLAUDE.md                    ← Claude Code-specific notes
├── justfile                     ← single command runner
├── .env.example                 ← copy to .env, fill secrets
│
├── docs/
│   ├── architecture.md          ← system diagram + data flow
│   ├── product-catalog.md       ← source-of-truth list of products we document
│   └── adr/                     ← Architecture Decision Records
│
├── prompts/                     ← versioned prompts (frontmatter + body)
│   ├── system/                  ← system prompts for the main agent
│   └── tools/                   ← per-skill prompt templates
│
├── evals/                       ← eval suite — runs before any agent change
│   ├── cases/                   ← golden test cases (YAML)
│   └── run.py
│
├── apps/
│   ├── frontend/                ← Astro + Preact chat island
│   └── backend/                 ← FastAPI orchestrator + MCP servers
│       ├── src/agent/           ← LangGraph state machine + LiteLLM client
│       └── mcp_servers/         ← one folder per skill (MCP-compliant)
│
└── packages/
    └── e2e/                     ← Playwright (evidence capture + smoke tests)
```

---

## Day-to-day commands

```powershell
just dev                # FE + BE + MCP servers
just dev-fe             # Astro only
just dev-be             # FastAPI only

just index              # (re)build ChromaDB index from docs/
just eval               # run the eval suite
just eval -- --case search-docs  # run one case

just screenshot <name>  # trigger Playwright evidence capture
just test               # run all tests (unit + e2e)

just mcp-inspect <skill>  # debug an MCP server with the Inspector
just mcp-list             # list all MCP servers
```

Full list: `just --list`.

---

## How to add a new product to the catalog

The doc format is strict on purpose — see [`docs/PRODUCT-DOC-FORMAT.md`](docs/PRODUCT-DOC-FORMAT.md). Quick path:

1. `cp -r docs/products/_template docs/products/<your-product-id>`
2. Fill in `product.md` (frontmatter + standard sections) and add `features/<feature>.md` for each non-trivial feature.
3. Add a row to [`docs/product-catalog.md`](docs/product-catalog.md) (the index).
4. Run `just index` to rebuild the vector store.
5. (Optional) Add an eval case under `evals/cases/` so the new product's answers don't regress.

---

## How to add a new skill

See [`apps/backend/mcp_servers/AGENTS.md`](apps/backend/mcp_servers/AGENTS.md). TL;DR:

1. Copy `mcp_servers/_template/` to `mcp_servers/<your_skill>/`.
2. Fill in `skill.md` (description, when-to-use, input/output examples).
3. Implement `server.py` exposing one or more MCP tools.
4. Register the server in `apps/backend/src/agent/mcp_clients.py`.
5. Add an eval case.

---

## Deployment

See [`docs/adr/0005-deployment-strategy.md`](docs/adr/0005-deployment-strategy.md).

- **Frontend**: pushed to `main` → Cloudflare Pages auto-builds.
- **Backend + MCP servers**: `docker compose up` on a small VPS, *or* `fly deploy` to Fly.io.
- **Vector index**: built in CI on doc changes; artifact pushed to BE container.

We deliberately avoid Next.js + EC2 — that combination caused the cost overrun on the previous project.
