# ADR 0009 — Enforced product scope + agent loop guard

- **Status**: Accepted
- **Date**: 2026-07-27
- **Amends**: ADR 0002 (MCP skills — the orchestrator may now rewrite one tool's arguments), ADR 0003 (LLM gateway — the pre-call token budget is now actually applied)

## Context

Two problems surfaced together in production use, and both came from the same
gap: the orchestrator delegated to the model decisions it should have been
making itself.

**1. The product scope was advisory.** The UI had a product picker whose value
travelled all the way to `AgentState.product_id` — and then stopped, becoming a
sentence in the system prompt asking the model to please pass `product_id` when
it called `search_documentation`. The tool read that argument from whatever the
model wrote. So the filter held only as long as the model chose to cooperate,
and there was no signal when it didn't. Compounding it, the picker was a chip
row above the composer with "all products" preselected, so in practice the
value was almost always unset anyway. A filter that defaults to off and is
enforced by persuasion is not a filter.

**2. The agent loop had no brake.** `build_graph()` wired `tools → llm`
unconditionally and `_route_after_llm` ended the graph only when the model
stopped requesting tools. A model that kept re-searching kept looping. The only
thing stopping it was LangGraph's default `recursion_limit` of 25 supersteps,
which was never set explicitly and therefore never reasoned about. Each round
costs one full-history LLM call plus an MCP subprocess spawn, and because every
tool result is appended to the history, the cost per round grows as the loop
runs. An observed incident ran ~12 rounds over roughly a minute before dying
with a `GraphRecursionError` that reached the user as a generic "something went
wrong".

Investigating (2) surfaced a third issue: `token_killer.prune_to_budget` — the
module the repo calls RTK, written specifically for this — was dead code on the
main path. `llm.acompletion` only prunes when handed `max_input_tokens`, and
`graph.call_llm` never passed it. Nothing was capping request growth.

## Decision

### Scope is enforced in the orchestrator, not requested in the prompt

`graph.call_tools` injects the selected `product_id` into `search_documentation`
arguments before dispatch, overwriting whatever the model supplied. This is the
only place in the codebase that rewrites a tool's arguments, and the exception
is deliberate: **a prompt is not an access control**. When the user picks a
product, every search that turn is provably within it.

`product_id = None` means the user explicitly chose "all products" and the model
keeps control of the argument, as before.

The prompt (main-agent v8) now *describes* the scope rather than implementing
it, and is explicit that omitting `product_id` will not widen the search — so
the model doesn't waste rounds trying.

Two supporting changes make the narrower scope safe:

- `search_documentation` returns an explicit `warning` on an empty result,
  naming the scope that was applied. An empty result used to be indistinguishable
  from "nothing worth reporting", which is exactly when a model starts filling
  gaps from memory.
- The FE turns the picker into an **entry gate**: the composer stays disabled
  until a scope is chosen, and the choice then lives in the header where it can
  be changed mid-conversation without losing the transcript. "All products"
  remains available as a visually secondary action, so it reads as a decision
  rather than a default.

### The loop is bounded, and ends with an answer

`AgentState` gains `tool_rounds`. On reaching `settings.agent_max_tool_rounds`
(6), `_route_after_llm` routes to a `final` node that makes one more LLM call
and returns an answer from the evidence already gathered. `server.py` also
passes an explicit `recursion_limit` derived from that budget, as a backstop
that is visible in the code rather than inherited.

**Forcing that answer needs an explicit instruction turn, not just an empty
tool list.** The obvious implementation — call the model with `tools=None` —
was built first and did not work. Verified against `gemini-3.5-flash` through
LiteLLM: with prior tool calls in the history the model keeps emitting
`tool_calls` and returns `content: None`, so the guard stopped the loop but the
user got an empty bubble. `tool_choice="none"` is not honoured for Gemini in
the installed LiteLLM version either. What works, and works on any provider, is
appending a user turn that says to stop searching and answer now — held in
`prompts/system/final-answer-nudge.md` per the prompts-are-code rule. `tools=None`
is kept as well, but it is belt and braces, not the mechanism.

The budget is checked *after* the model has emitted its next batch of tool
calls, so the history at that point ends with a request the graph refused to
run. That dangling call is stripped before the final call
(`_drop_unanswered_tool_calls`) — leaving it in was a second cause of empty
completions.

`graph.call_llm` now passes `settings.agent_max_input_tokens` (60k), which
switches RTK on. Pruning had to become **tool-exchange aware** first: dropping
an assistant `tool_calls` message while keeping its `role="tool"` replies
produces an orphaned `tool_call_id`, which providers reject outright — turning
a cost optimisation into a hard failure. `token_killer.group_tool_exchanges`
keeps a call and its replies together as one indivisible unit.

## Consequences

**Good**

- Scope is a guarantee, testable without an LLM (`test_graph.py`) instead of a
  behaviour to be spot-checked.
- Runaway loops cost at most 6 rounds and end with usable prose rather than an
  error the user can't act on.
- RTK finally runs, capping request growth on long conversations.
- Disabling Langfuse when credentials are absent removes the recurring
  "Failed to export span batch" retry noise that was burying real errors.

**Costs and risks**

- A genuinely cross-product question asked while focused on one product will
  come back empty. Mitigated by the empty-result warning plus the prompt rule
  telling the agent to suggest switching focus — but it is a real behaviour
  change, and "all products" exists for exactly this.
- The tool-round budget can truncate legitimate multi-step research. 6 is
  roughly double what a well-formed answer needs; if that proves tight the
  setting is one env-adjacent constant, not a code change.
- `_SCOPED_TOOL` couples the orchestrator to the `search_documentation` tool
  name. Renaming that skill silently disables enforcement; the eval case in
  `evals/cases/scope/` is what catches it.

## Alternatives considered

- **Leave scope in the prompt, just make the UI louder.** Rejected: it fixes
  the "nobody sets it" half and none of the "the model may ignore it" half.
  Prompt compliance is not a mechanism you can test.
- **Strip `product_id` from the tool schema when a scope is set.** Would also
  work, but the tool catalogue is cached module-level and shared across
  requests, while scope is per-request. Injecting at dispatch keeps the cache
  intact and the enforcement in one readable place.
- **Lock scope for the whole conversation (changing it starts a new chat).**
  Rejected as too rigid: switching focus to follow a train of thought is
  ordinary usage, and the transcript is still useful across the switch.
- **Hard-error when the loop budget is hit.** Rejected: the user asked a real
  question and the agent usually has enough retrieved evidence to answer it.
  Stopping the spend does not require withholding the answer.
- **Stop the loop with `tools=None` or `tool_choice="none"` alone.** Tried
  both; neither stops Gemini mid-loop (see Decision above). Kept `tools=None`
  as defence in depth, but the instruction turn is what makes it work.
- **Pool MCP sessions instead of spawning per tool call.** Deferred. It is the
  bigger cost lever (~500ms plus model load per call, see the `mcp_clients`
  docstring), but it is a latency/throughput change, not a correctness one, and
  it deserves its own ADR.
