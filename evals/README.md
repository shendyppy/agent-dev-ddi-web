# Eval suite

The agent's quality is **only as good as the evals that gate it**. Every change to a prompt, a skill, the LLM model, or the retrieval pipeline must be evaluated against this suite before shipping.

## Running

```powershell
just eval                            # run everything, real model, rubric judged
just eval --case scope               # one group folder, case name, or file stem
just eval --tag prompt:main-agent    # all cases tagged with a prompt
just eval --fast                     # no model call — see "Fast mode" below
just eval --no-judge                 # real model, skip rubric scoring
```

Exit code is 1 if any hard assertion failed, so `just` and CI both stop on a regression. Results land in `evals/.runs/<timestamp>/` — `summary.json` plus one file per case with the full trace.

Cases run **sequentially**. The default model is a free-tier Gemini key capped around 20 requests/day; a parallel run turns that budget into rate-limit errors that look like agent failures.

## Fast mode

`--fast` sets `LLM_FAKE_MODE`, so no provider is called. `agent.llm._fake_completion` emits one synthetic `search_documentation` call using the **raw user question**, then renders an answer from the real chunks that come back.

That makes fast mode meaningful but narrow:

| Enforced | Not enforced |
|---|---|
| the graph runs at all | which tools the model chooses |
| scope injection (`tool_args_must_include`) | how many rounds it takes |
| retrieval (`must_retrieve_any`) | anything about the answer text |

Model-dependent assertions are reported as **skipped**, never as passed — a green fast run tells you nothing about a prompt change. The console prints exactly which checks were skipped and how many were actually enforced.

Because fast mode searches the raw question rather than a model-rewritten one, it is also the mode that measures retrieval honestly: a full run can pass a retrieval assertion simply because the model translated the question into English first.

CI runs `--fast` only. Full runs cost real quota and stay local.

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
  must_call_tool:
    - search_documentation
  must_contain_any:
    - "pnpm dev"
    - "npm run dev"
  must_not_contain:
    - "I'm not sure"
    - "I don't have access"

  # Soft checks — scored, reported, do not fail the case
  rubric:
    - "Includes a `Sources:` section citing the catalog."
    - "Answer is under 200 words."
```

Only assertions you actually declare are checked. An omitted `must_not_contain` produces no result at all rather than a vacuous pass, so the report's "N assertions enforced" count means something.

`input.product_id` mirrors the UI product picker. `null` is the explicit "all products" choice, and the difference matters: with a scope set the orchestrator rewrites every `search_documentation` call's `product_id` (ADR 0009).

### Full assertion vocabulary

| Key | Checks |
|---|---|
| `must_call_tool` | every listed tool was invoked at least once |
| `must_call_tool_in_order` | when true, reads `must_call_tool` as a sequence (others may interleave) |
| `tool_args_must_include` | every call to the named tool carried these argument values — *every*, not *some*, because the scope guarantee is that none escape |
| `max_tool_rounds` | the tools node ran at most N times |
| `must_retrieve_any` | at least one listed path appears in what `search_documentation` returned |
| `must_contain_any` | at least one string appears in the final answer |
| `must_not_contain` | none of these strings appear in the final answer |
| `rubric` | scored by a judge model — advisory, never fails the case |

### `must_retrieve_any` — why retrieval gets its own assertion

The text checks pass just as happily when the model guessed correctly from a bad retrieval. This one is checked against the `source` metadata `search_documentation` actually returned, so it fails when the right document never reached the model — even if the answer came out right anyway. Retrieval bugs and generation bugs need different fixes, so they need different assertions.

Paths match on substring, so `acelents/product.md` is enough — no need to pin the folder layout.

### Text matching

`must_contain_any` / `must_not_contain` match case-insensitively on a **leading word boundary**, not plain substring. That is not a nicety: `"npm install"` is a substring of `"pnpm install"`, so the Acelents case's blocklist used to fail every *correct* answer. Needles starting with punctuation (`![`, `/screenshots/`) fall back to substring. Prefix patterns like `ZEPHYR_SSO_` still match `ZEPHYR_SSO_ENABLED`, since only the leading edge is bounded.

## Known gaps

A case may declare an assertion that does not pass yet:

```yaml
known_gap:
  checks: [must_retrieve_any]
  tracked_in: "Fase 2a — ADR-0010 (multilingual embeddings)"
  reason: >
    Why it fails today, with the measurement that shows it.
```

The check still runs and still reports its real state; it just does not fail the build, and the summary lists every open gap with its reason. The point is to avoid the two usual outcomes — weakening the assertion until it matches the defect (which makes the defect the spec), or leaving the suite red until everyone ignores it.

If a marked check starts passing, the report says so and asks for the marker to be removed. Write the assertion against the behaviour you want, not the behaviour you have.

## Case groups

```
evals/cases/
├── search-docs/         ← retrieval quality
├── scope/               ← product scope enforcement + loop guard (ADR 0009)
├── catalog/             ← list_products, check_app_health
├── capture-screenshot/  ← capture_screenshot decision making
└── refusal/             ← cases where the agent should refuse / clarify
```

## How the rubric is judged

Soft rubric items go to a judge model via `prompts/system/eval-judge.md`, which scores each item `pass` / `partial` / `fail` **against the retrieved sources only** — a judge reasoning from its own knowledge would bless answers that invented details, which is the exact failure the rubric exists to catch.

Rubric results are advisory. Wiring quality opinions to a red build is how rubrics get deleted. A judge outage is recorded as a judge error, not a case failure.

## How it runs

`runner.py` replays the case through the same `graph.ainvoke` that `POST /api/chat` uses — same nodes, same scope injection, same tool-round budget. An eval that exercised a parallel code path would prove nothing about the code that ships.

`checks.py` holds the assertions and imports nothing from `agent.*`, so `just test-evals` runs in milliseconds without a model, an index, or an MCP subprocess. Those tests matter: an assertion that silently never fires looks exactly like one that passes.

## Adding a case (canonical flow)

1. Identify the behavior you want to lock in.
2. Pick a group folder (or make a new one).
3. Write the case as YAML.
4. Run `just eval -- --case <your_case>` and confirm it passes.
5. Commit. Now any future change that breaks it gets caught.

## Coverage

Aim for:

- 1 happy-path case per skill
- 1 refusal case per ambiguity class
- 1 regression case per bug fix

Currently thin: 8 of the 10 knowledge-base products have no case at all, and there is nothing covering the offline / `LLM_FAKE_MODE` answer path itself.
