# Backend — FastAPI orchestrator + MCP servers

See [`AGENTS.md`](AGENTS.md) for conventions when editing this folder.

## Layout

```
apps/backend/
├── pyproject.toml         ← uv-managed
├── src/
│   ├── agent/             ← orchestrator package
│   │   ├── server.py      ← FastAPI app + SSE /chat endpoint
│   │   ├── graph.py       ← LangGraph state machine
│   │   ├── llm.py         ← LiteLLM wrapper (Langfuse-traced)
│   │   ├── prompts.py     ← prompt loader (reads ../../prompts/)
│   │   ├── mcp_clients.py ← MCP client registry + server lifecycle
│   │   ├── indexing.py    ← ChromaDB indexer (run via `just index`)
│   │   └── settings.py    ← pydantic-settings env loader
│   └── mcp_servers/       ← one folder per skill (see AGENTS.md there)
│       ├── _template/
│       ├── search_docs/
│       ├── list_products/
│       ├── capture_screenshot/
│       └── check_app_health/
└── tests/
```

## Commands

```powershell
just dev-be        # uvicorn with reload
just test-be       # pytest
just lint          # ruff check
just index         # rebuild ChromaDB index
just mcp-list      # list configured MCP servers
just mcp-inspect search_docs   # MCP Inspector for one skill
```

## Environment

Reads from the repo-root `.env` file. See `.env.example` for required keys.
