# apps/backend — AGENTS.md

Conventions for editing the backend. Read repo-root [`AGENTS.md`](../../AGENTS.md) first.

## Layout reminder

```
src/
├── agent/             ← orchestrator (FastAPI + LangGraph + LiteLLM)
└── mcp_servers/       ← skills as MCP servers (one folder each)
```

## Rules specific to this folder

1. **LLM access**: only via `agent.llm.acompletion`. Importing `litellm` or `anthropic` elsewhere is a bug.
2. **Settings access**: only via `agent.settings.settings`. Don't read `os.environ` directly.
3. **Prompts**: load via `agent.prompts.load(...)`. Don't inline.
4. **Skills**: live as MCP servers under `mcp_servers/`. Never add a `@tool`-decorated function in `agent/graph.py`.
5. **Tests**: `pytest`. Tests live alongside source (`foo.py` → `test_foo.py`).
6. **Async**: prefer `async def` for any I/O. Sync I/O in handlers blocks the event loop.

## Common patterns

### Adding a new env var

1. Add it to `agent/settings.py` as a typed field on `Settings`.
2. Add it to repo-root `.env.example` with a comment.
3. Reference via `settings.your_field`.

### Adding a new endpoint

1. Add to `agent/server.py`.
2. Use Pydantic models for request/response — no raw dicts on the API boundary.
3. If long-running, return SSE via `sse_starlette.EventSourceResponse`.

### Adding a new tool to the agent

This is **not** a backend task — it's a skill. See [`src/mcp_servers/AGENTS.md`](src/mcp_servers/AGENTS.md).

## Running locally

```powershell
just dev-be              # uvicorn with reload, port 8000
just test-be             # pytest
just lint                # ruff check
just index               # build ChromaDB index from docs/
just mcp-inspect <skill> # debug a single MCP server
```
