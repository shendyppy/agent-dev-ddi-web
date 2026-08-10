# CLAUDE.md — Claude Code specific notes

This file supplements [`AGENTS.md`](AGENTS.md) with Claude Code–specific tips. Read AGENTS.md first; only the deltas below are Claude Code–specific.

## Environment

- **OS**: Windows 11. Shell is **PowerShell** (use `$null`, `$env:VAR`, backtick line-continuation). Bash is available via the Bash tool for POSIX scripts when needed.
- **Build runner**: `just` (installed via `scoop install just`). Always prefer `just <recipe>` over raw commands.
- **Python**: invoked via `uv run` — do **not** activate venvs manually.

## When asked to add a skill

The canonical flow is in [`AGENTS.md`](AGENTS.md#adding-a-new-skill-most-common-task). Reminder: **skills are MCP servers**, not inline tools. If you find yourself writing a `@tool` decorator, stop and reconsider.

## When asked to debug a bad RAG answer

1. Pull the trace from Langfuse (`just trace <session_id>`).
2. Inspect what `search_documentation` returned to the LLM.
3. If retrieval is wrong → fix indexing or the embedding query (test in isolation with `just mcp-inspect search_docs`).
4. If retrieval is right but generation is wrong → fix the prompt in `prompts/`.
5. Add an eval case that catches this regression before you ship the fix.

## Long-running / background tasks

- `just dev` runs FE + BE + MCP servers concurrently. Use `run_in_background: true` when invoking it via Bash.
- The eval suite can be slow (calls real LLM). Run with `--fast` flag for cached/mocked mode during iteration.

## Things you might be tempted to do (don't)

- **Don't** run `pip install` directly. Use `uv add <pkg>` so it lands in `pyproject.toml` + lockfile.
- **Don't** go looking for `apps/backend/main.py` — it was the pre-MCP entry point and ADR 0007 removed it. The real entry point is `apps/backend/src/agent/server.py`.
- **Don't** rewrite the Makefile. It exists only as a thin delegator to `just` for muscle-memory; canonical recipes are in `justfile`.
- **Don't** suggest deploying to EC2. The previous project hit cost overruns there — see [`docs/adr/0005-deployment-strategy.md`](docs/adr/0005-deployment-strategy.md).

## Useful skills (Claude Code skills, not chatbot skills)

These are likely relevant during development:

- `/init` — only if AGENTS.md/CLAUDE.md ever get out of sync with the codebase.
- `/verify` — after implementing a feature, verify by running the app and screenshotting the result.
- `/simplify` — after a non-trivial change, review for unnecessary complexity.
- `/security-review` — before shipping anything touching auth, secrets, or external input.
- `/review` — for PR review.

## Quick map: where do I edit what?

| User asks for... | You edit... |
|---|---|
| "Make the agent answer faster" | `prompts/system/main-agent.md` (instructions) or `apps/backend/src/agent/graph.py` (parallelize tool calls) |
| "Add screenshot capability for X" | `packages/e2e/tests/<x>.spec.ts` + register scenario in `apps/backend/src/mcp_servers/capture_screenshot/` |
| "Index this new product's docs" | `docs/product-catalog.md` + `apps/backend/src/agent/indexing.py` sources |
| "Swap to GPT-4o" | `.env` (`LITELLM_MODEL=gpt-4o`). No code change. |
| "Add a new chat UI feature" | `apps/frontend/src/components/Chat.tsx` (Preact island) |
