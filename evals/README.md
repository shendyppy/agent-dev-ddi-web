# Eval suite

The agent's quality is **only as good as the evals that gate it**. Every change to a prompt, a skill, the LLM model, or the retrieval pipeline must be evaluated against this suite before shipping.

## Running

```powershell
just eval                            # run everything
just eval -- --case search-docs      # one case directory
just eval -- --tag prompt:main-agent # all cases tagged with a prompt
just eval -- --fast                  # cached/mocked LLM calls where possible
```

Results land in `evals/.runs/<timestamp>/` with a summary printed to console.

## Case format

Each case is a YAML file under `evals/cases/<group>/<case_name>.yaml`:

```yaml
name: search-product-run-instructions
tags: [prompt:main-agent, skill:search_documentation]
description: |
  When a user asks how to run a known product, the agent should return
  the exact command from the catalog, not paraphrase or invent.

input:
  messages:
    - role: user
      content: "How do I run the Example Product locally?"

expected:
  # Hard requirements — case fails if any are violated
  must_contain_any:
    - "pnpm dev"
    - "npm run dev"
  must_call_tool:
    - search_documentation
  must_not_contain:
    - "I'm not sure"
    - "I don't have access"

  # Soft checks — scored, reported, do not fail the case
  rubric:
    - "Includes a `Sources:` section citing the catalog."
    - "Answer is under 200 words."
```

## Case groups

```
evals/cases/
├── search-docs/         ← retrieval quality
├── capture-screenshot/  ← capture_screenshot decision making
└── refusal/             ← cases where the agent should refuse / clarify
```

## How `must_call_tool` is checked

We capture the tool-use trace from the LangGraph run. The case passes if every listed tool was invoked at least once. Order is not enforced unless you set `must_call_tool_in_order: true`.

## How the rubric is judged

Soft rubric items are evaluated by a separate "judge" LLM call (Claude Sonnet 4.6) that scores each rubric item independently. Used for trend tracking, not pass/fail.

## Adding a case (canonical flow)

1. Identify the behavior you want to lock in.
2. Pick a group folder (or make a new one).
3. Write the case as YAML.
4. Run `just eval -- --case <your_case>` and confirm it passes.
5. Commit. Now any future change that breaks it gets caught.

## Bootstrap state

The suite starts mostly empty. As you ship features, add cases for each. Aim for:

- 1 happy-path case per skill
- 1 refusal case per ambiguity class
- 1 regression case per bug fix
