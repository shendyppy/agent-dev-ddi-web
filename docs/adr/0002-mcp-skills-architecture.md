# ADR 0002 — Skills as MCP servers

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

The agent needs a growing set of capabilities ("skills" / "tools"): RAG search, screenshot capture, app health checks, product listing, etc. Two common patterns exist:

1. **Inline tools**: skills defined as Python functions decorated with `@tool` and registered with LangGraph directly.
2. **External tool servers**: skills run as separate processes exposing the **Model Context Protocol (MCP)**.

## Decision

All skills are implemented as **MCP servers** — one folder per skill under `apps/backend/src/mcp_servers/<name>/`. The FastAPI orchestrator connects via an MCP client.

## Why

| Concern | Inline tools | MCP servers |
|---|---|---|
| Reusable in Claude Desktop / Cursor | ❌ | ✅ |
| Forces clean I/O boundary | ⚠️ Easy to break | ✅ Protocol-enforced |
| Testable in isolation (MCP Inspector) | ❌ | ✅ |
| Can be deployed independently if scale demands | ❌ | ✅ |
| Skill description doubles as prompt for LLM tool selection | Manual | Auto from `skill.md` |
| Onboarding cost | Low | Medium (read MCP spec once) |
| Process overhead at dev time | None | One subprocess per skill |

The portability + boundary discipline outweigh the one-time onboarding cost. We will likely want to expose these skills to Claude Desktop for internal team use anyway.

## Structure of an MCP server in this repo

```
apps/backend/src/mcp_servers/<skill_name>/
├── skill.md           ← human-readable spec — also parsed to generate MCP tool description
├── server.py          ← MCP server entrypoint (uses `mcp` Python SDK)
├── handler.py         ← actual implementation (pure functions, easy to unit-test)
└── test_handler.py    ← unit tests
```

`skill.md` frontmatter:

```yaml
---
name: search_documentation
version: 1
inputs:
  query: string
  top_k: integer (default 5)
outputs:
  chunks: list of {text, source, score}
when_to_use: |
  When the user asks about documentation, features, run instructions,
  or anything about a specific product in the catalog.
---
```

## Consequences

**Positive:**
- Skills are portable. Adding a new skill is a self-contained PR.
- Clean separation between "what skill does" (server) and "how agent decides to use it" (graph + prompt).
- New devs (and AI agents) only need to read one `skill.md` to add capability.

**Negative:**
- One extra layer of indirection vs `@tool` decorators.
- Process management (starting/stopping MCP servers in dev) — handled by the orchestrator's MCP client config.

## See also

- MCP spec: https://modelcontextprotocol.io
- [ADR 0003 — LLM via LiteLLM](0003-llm-via-litellm.md)
