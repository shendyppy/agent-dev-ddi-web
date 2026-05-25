# prompts/ — Versioned prompts

Prompts are **first-class artifacts**. Treat them like code: review, version, eval-gate every change.

## Folder layout

```
prompts/
├── AGENTS.md            ← this file
├── system/              ← system prompts for the main agent (one per persona/mode)
│   └── main-agent.md
└── tools/               ← per-skill prompt templates (rare — most skills derive prompt from skill.md)
    └── search-docs.md
```

## File format

Every prompt file is Markdown with YAML frontmatter:

```markdown
---
name: main-agent
version: 1
model: claude-sonnet-4-6     # advisory — the orchestrator may override
description: System prompt for the primary documentation assistant.
inputs:                       # template variables expected by the loader
  - product_catalog
  - current_date
last_evaluated: 2026-05-25
---

# Body

The actual prompt text. May reference `{{product_catalog}}` etc. — these
are substituted by `agent/prompts.py` at runtime.
```

## Rules

1. **Bump `version` for any semantic change.** Even a typo fix if it changes meaning.
2. **Update `last_evaluated`** to today's date after running eval cases against the new version.
3. **Never** hardcode a multi-line prompt in `.py` files. Load via `agent.prompts.load("main-agent")`.
4. **Add an eval case** under `evals/cases/` for any new behavior the prompt is meant to drive.
5. Keep prompts as short as they can be. Long preamble = more tokens per call = slower + costlier.
6. Prefer **examples in the prompt over rules** when behavior is hard to specify abstractly.

## How the loader works

`agent.prompts.load(name)` reads `prompts/system/<name>.md` (or `prompts/tools/<name>.md`), parses frontmatter, and returns a `Prompt` object with a `.render(**kwargs)` method that fills `{{placeholders}}`.
