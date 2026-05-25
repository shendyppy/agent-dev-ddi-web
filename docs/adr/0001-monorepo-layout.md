# ADR 0001 — Monorepo layout

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

We need one repo to hold:
- A frontend (chat UI)
- A backend orchestrator (Python)
- Multiple skills (Python MCP servers)
- An e2e/automation package (Playwright/TypeScript)
- Versioned prompts, evals, and docs

Two languages (Python + TypeScript), multiple deployables, and shared docs/prompts/evals.

## Decision

Use a **monorepo** with this layout:

```
apps/         ← deployable applications
  frontend/   ← Astro
  backend/    ← FastAPI + MCP servers (same Python project)
packages/     ← shared libraries / cross-cutting tooling
  e2e/        ← Playwright suite
docs/         ← architecture, ADRs, product catalog
prompts/      ← versioned prompts (cross-cutting, used by backend)
evals/        ← eval suite (cross-cutting)
```

JS workspaces (pnpm) for frontend + e2e. A single Python project (`uv`) for the backend including all MCP servers.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Polyrepo (one per app) | Prompts and ADRs would fragment; eval coverage hard to maintain; "is the prompt change deployed?" gets confusing |
| Monorepo with separate Python projects per MCP server | Premature splitting; uv handles multi-package well within one project; can split later if any skill grows huge |
| Nx / Turborepo | Adds heavyweight tooling for a 3-package repo; `just` + `pnpm workspaces` + `uv` suffice |

## Consequences

**Positive:**
- Single PR can touch FE + BE + eval + prompt — one review unit.
- Shared `docs/`, `prompts/`, `evals/` are colocated with the code they govern.
- One `just bootstrap` brings everything up.

**Negative:**
- CI must understand which deployables are affected by a change (mitigated by per-app filters).
- Cross-language tooling (Python + TS) requires both toolchains installed locally.

## See also

- [ADR 0002 — MCP skills architecture](0002-mcp-skills-architecture.md)
