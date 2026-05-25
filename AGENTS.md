# AGENTS.md — Repo conventions for AI coding agents

> If you are an AI coding agent (Claude Code, Cursor, Aider, Copilot Workspace, etc.) working in this repo: **read this file first**, every session. It is the source of truth for how to navigate, edit, and ship changes here.
>
> If you are a human: this doubles as your onboarding doc.

---

## What this project is

A documentation chatbot. Users ask natural-language questions about products we maintain ("how do I run X?", "what features does Y have?", "screenshot the login flow"). The agent answers using RAG over our docs and, when needed, invokes Playwright to capture live UI evidence.

The product itself is AI. The *development process* is also AI-first — meaning this codebase is structured so that you (the AI agent) can be productive without a human re-explaining context.

---

## Core principles you MUST follow

### 1. Prompts are code

Prompts live in [`prompts/`](prompts/) as `.md` files with frontmatter. **Never** hardcode a multi-line prompt inside a `.py` file. Load it from `prompts/` via the prompt loader (`apps/backend/src/agent/prompts.py`).

Why: prompts need diff-able history, code review, and eval-gated changes. Inline strings can't be reviewed properly.

### 2. Every agent-behavior change needs an eval case

Before changing a prompt, skill, or model — add (or update) a case under [`evals/cases/`](evals/cases/). Run `just eval` and confirm the case passes before AND after your change.

Why: without evals, RAG quality regresses silently. We have no other way to know.

### 3. Skills are MCP servers, not inline Python functions

A new tool/skill goes into [`apps/backend/mcp_servers/<name>/`](apps/backend/mcp_servers/), exposing the MCP protocol. The orchestrator connects via an MCP client. **Do not** define skills as LangGraph `@tool` decorators directly on the graph.

Why: MCP makes skills reusable from Claude Desktop, Cursor, and other clients. It also forces a clean interface boundary.

### 4. Single command runner: `just`

Any new dev workflow gets a recipe in [`justfile`](justfile). **Do not** add npm scripts, Python entry-points, or PowerShell scripts as the primary interface. They can exist, but `just` is the front door.

Why: consistency. AI agents and humans should never have to guess how to start something.

### 5. Observability hari-1

Every LLM call must route through `apps/backend/src/agent/llm.py` (LiteLLM wrapper) which auto-traces to Langfuse. **Do not** call `anthropic.Anthropic()` / `openai.OpenAI()` / `litellm.completion()` directly anywhere else in the codebase.

Why: without traces, debugging a bad RAG response is guessing.

### 6. Architectural decisions go in `docs/adr/`

When you make a non-trivial architectural choice (new framework, new service, new pattern), write an ADR. Numbered, dated, with **Context / Decision / Consequences**. See existing ADRs for the format.

Why: future-you (and future-AI) needs to know *why*, not just *what*.

---

## How to navigate this repo

| What you want | Where to look |
|---|---|
| System overview | [`docs/architecture.md`](docs/architecture.md) |
| Why we chose X | [`docs/adr/`](docs/adr/) |
| List of products we document | [`docs/product-catalog.md`](docs/product-catalog.md) |
| Main agent loop | [`apps/backend/src/agent/graph.py`](apps/backend/src/agent/graph.py) |
| LLM client (always go through this) | [`apps/backend/src/agent/llm.py`](apps/backend/src/agent/llm.py) |
| Existing skills | [`apps/backend/mcp_servers/`](apps/backend/mcp_servers/) |
| Existing prompts | [`prompts/`](prompts/) |
| Eval cases | [`evals/cases/`](evals/cases/) |
| Frontend chat UI | [`apps/frontend/src/components/Chat.tsx`](apps/frontend/src/components/) |
| Playwright scenarios | [`packages/e2e/tests/`](packages/e2e/) |

Each major folder has its own `AGENTS.md` with folder-specific conventions. Read it when you enter that folder.

---

## Common tasks — the canonical flow

### Adding a new skill (most common task)

1. Read [`apps/backend/mcp_servers/AGENTS.md`](apps/backend/mcp_servers/AGENTS.md).
2. `cp -r apps/backend/mcp_servers/_template apps/backend/mcp_servers/<skill_name>`
3. Edit `skill.md` — describe what the skill does, when the LLM should call it, input/output examples. **This file is parsed to generate the MCP tool spec.**
4. Implement `server.py`.
5. Register the server in `apps/backend/src/agent/mcp_clients.py`.
6. Add eval case under `evals/cases/<skill_name>/`.
7. `just eval` — confirm pass.
8. `just dev` — manual smoke test from the chat UI.

### Changing a prompt

1. Edit the relevant `.md` in `prompts/`.
2. Bump `version:` in frontmatter.
3. Run relevant eval cases: `just eval -- --tag <prompt-name>`.
4. If quality drops, iterate or revert.

### Adding a new product to the doc corpus

1. Edit `docs/product-catalog.md` — add product entry.
2. Add product docs/README path to `apps/backend/src/agent/indexing.py` sources list.
3. `just index` — rebuild ChromaDB.
4. Optionally add an eval case that asks about the new product.

---

## What NOT to do

- ❌ Don't call LLM providers directly. Always via `llm.py`.
- ❌ Don't add skills as inline LangGraph tools. Always as MCP servers.
- ❌ Don't inline prompts as Python strings. Always in `prompts/`.
- ❌ Don't add Next.js, React, or heavy SPA frameworks. Astro is intentional.
- ❌ Don't introduce a new build runner (npm scripts, poethepoet, tox, etc.). `just` only.
- ❌ Don't commit `.env`. Use `.env.example` as the template.
- ❌ Don't ship an agent change without an eval case proving it works.
- ❌ Don't add comments like `# Implements X` or `// added for Y` — code names should be self-explanatory.

---

## Style & conventions

- **Python**: ruff for lint + format. Type hints required for public functions. Pydantic for any data crossing a process boundary (HTTP, MCP, file).
- **TypeScript**: strict mode. Prefer Preact's `useState` over global state libs.
- **Tests**: pytest for Python, Playwright for e2e. Unit tests next to source (`foo.py` → `test_foo.py`).
- **Commits**: imperative mood. Reference ADR or eval case if relevant.

---

## When you're unsure

- Check the relevant folder's `AGENTS.md`.
- Search ADRs (`docs/adr/`) for prior decisions.
- Look at how an existing skill / prompt / case is structured and mirror it.
- If still unsure, **ask the human** before making a structural change. Implementing the wrong thing wastes their review time.
