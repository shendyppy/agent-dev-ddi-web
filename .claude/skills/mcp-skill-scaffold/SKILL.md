---
name: mcp-skill-scaffold
description: Use when adding a new runtime skill to the agent (an MCP server under apps/backend/mcp_servers/). Triggers on "add a skill that <verb> <thing>", "give the agent the ability to <X>", "new tool for <Y>". Automates the canonical 'Adding a new skill' flow from AGENTS.md (cp template → edit skill.md → implement server → register client → eval → smoke).
---

# mcp-skill-scaffold

You are scaffolding a new MCP-server skill. In this repo, "skill" = an MCP server, never a `@tool` decorator. The canonical flow lives in [`AGENTS.md`](../../../AGENTS.md#adding-a-new-skill-most-common-task); this skill executes that flow end-to-end and stops you forgetting a step.

## Pre-flight (always do first)

1. Read [`apps/backend/mcp_servers/AGENTS.md`](../../../apps/backend/mcp_servers/AGENTS.md) — folder-specific conventions may have drifted from the top-level doc.
2. Confirm the skill name with the user. Naming rule: lowercase snake_case, verb-first, no `_skill`/`_tool` suffix (e.g., `capture_screenshot`, not `screenshot_skill`).
3. Check the skill does not already exist: `ls apps/backend/mcp_servers/`.
4. Identify one existing skill that is structurally closest to the new one and use it as the reference, not just the `_template/`.

## Scaffold steps (run in order)

### 1. Copy the template

```powershell
Copy-Item -Recurse apps/backend/mcp_servers/_template apps/backend/mcp_servers/<skill_name>
```

(Use `cp -r` via Bash if PowerShell is awkward in your context.)

### 2. Edit `skill.md`

This file is parsed to generate the MCP tool spec — get it right. Required sections:

- **Purpose** (1–2 sentences): what user-visible problem this solves.
- **When the LLM should call this** (3–5 bullets): trigger phrases or task shapes. Be concrete; "use when the user asks anything about X" is too broad.
- **Inputs**: each arg with type, required/optional, example value.
- **Outputs**: shape of the return (cite Pydantic model name if applicable).
- **Failure modes**: what the skill returns on timeout, missing data, upstream 5xx.
- **Side effects** (if any): file writes, network calls, cost implications.

If you cannot fill any of these confidently, **stop and ask the user**. A vague skill.md produces a skill the LLM never calls or calls wrongly.

### 3. Implement `server.py`

- Pydantic input/output models at the top.
- One `@app.tool()` function per public action. Keep skills focused — if the new skill exposes 5 actions, it is probably 2 skills.
- Any LLM call inside the skill must go through `from agent.llm import acompletion` — never `litellm`/`openai`/`anthropic` directly.
- External HTTP via `httpx`, with explicit `timeout=`. No silent retries; let the orchestrator decide.
- Type hints on every public function. `ruff` will lint, `mypy` may run in CI.

### 4. Register the server

Add the entry to [`apps/backend/src/agent/mcp_clients.py`](../../../apps/backend/src/agent/mcp_clients.py). Match the existing registration style (typically a transport spec + command). If the file uses a registry dict, add the key; if a factory list, append.

### 5. Add eval coverage

Under `evals/cases/<skill_name>/`, write at least:

- **Happy path** (one case): the LLM should call the skill given a trigger phrase.
- **Negative** (one case): the LLM should NOT call the skill on an unrelated query (catches over-triggering).
- **Edge** (one case): malformed or boundary input is handled gracefully.

Eval format mirrors existing cases — do not invent a new schema. If unsure, use the `rag-eval` skill to author the case shape.

### 6. Verify

```sh
just eval              # full suite must pass
just mcp-inspect <skill_name>   # interactive smoke test of the server alone
just dev               # exercise from chat UI end-to-end
```

### 7. Document

- If the skill introduces a new architectural pattern (new external service, new auth scheme, new persistence), write an ADR in `docs/adr/`.
- Otherwise: nothing extra. The `skill.md` + eval cases + code are the documentation.

## Output format when invoked

Report back to the user:

1. Skill name + one-line purpose.
2. List of files created/modified (paths only).
3. Eval cases added (IDs).
4. Smoke-test result (`just mcp-inspect` output summary).
5. Anything you stubbed and want them to review (e.g., placeholder API key, TODO in a prompt).

## Do not

- Do not skip the eval cases "to save time". This is the only thing that protects future changes from breaking the skill.
- Do not add the skill as a LangGraph `@tool`. That bypass is explicitly forbidden — see [`AGENTS.md`](../../../AGENTS.md#what-not-to-do).
- Do not import an LLM SDK in the skill module. Use `agent.llm`.
- Do not write a multi-paragraph docstring on the server function — `skill.md` is the spec.
- Do not commit a `.env` containing a new key. Add the var to `.env.example` with a placeholder.
