# mcp_servers/ — AGENTS.md

Each subfolder here is **one MCP server = one skill**. Per ADR 0002, this is the only way skills are added to the agent.

## Adding a new skill

1. **Copy the template**:
   ```powershell
   Copy-Item -Recurse src/mcp_servers/_template src/mcp_servers/<your_skill>
   ```

2. **Edit `skill.md`** — this is the canonical spec. Frontmatter fields:
   ```yaml
   ---
   name: your_skill              # matches folder name, snake_case
   version: 1
   inputs:
     query: string
     top_k: integer (default 5)
   outputs:
     result: ...
   when_to_use: |
     Plain-English description of when the LLM should call this skill.
     This text is shown to the LLM as the tool description — be precise.
   ---
   ```

3. **Implement `handler.py`** — pure async functions, no MCP-specific code. Easy to unit-test.

4. **Implement `server.py`** — MCP server entry-point. Wires `handler.py` functions to MCP tools using `mcp.server`.

5. **Add unit tests** in `test_handler.py`.

6. **Register the server** in `apps/backend/src/agent/mcp_clients.py` (`SERVERS` list).

7. **Add an eval case** under `evals/cases/<your_skill>/`.

8. **Smoke test**:
   ```powershell
   just mcp-inspect <your_skill>     # opens MCP Inspector UI
   just eval -- --case <your_skill>
   ```

## Rules

- Handlers are **pure async functions**. Side effects (filesystem, network) are explicit dependencies passed in.
- Inputs validated by **Pydantic models**. Output is JSON-serializable.
- Never import from `agent.*` inside an MCP server — servers must be runnable standalone.
- Errors propagate as structured JSON (`{"error": "...", "code": "..."}`), not exceptions through MCP.

## Existing skills

| Skill | Status | What it does |
|---|---|---|
| `_template` | scaffold | Copy this to start a new skill |
| `search_docs` | partial | RAG search over ChromaDB |
| `list_products` | stub | List products from the catalog |
| `capture_screenshot` | stub | Trigger Playwright scenario, return screenshot URL |
| `check_app_health` | stub | Check if a product is running |
