# ADR 0003 — LLM access via LiteLLM, default Claude Sonnet 4.6

- **Status**: Accepted
- **Date**: 2026-05-25

> **Runtime default changed, 2026-08-07.** The default is now
> `gemini/gemini-3.6-flash` (`settings.litellm_model`, `.env.example`), not
> `claude-sonnet-4-6`. The title and the "Why Claude as default" section below
> are left as written — they record what was decided on 2026-05-25.
>
> The swap needed no code change, which is the decision in this ADR working as
> intended rather than being reversed: the gateway and the "nothing imports a
> provider SDK directly" rule both still hold. What the swap *did* surface is a
> constraint this ADR did not anticipate — the free Gemini tier caps at ~20
> requests/day/model, which is why `agent/llm.py` grew quota classification and
> an offline fallback window. That mechanism is still undocumented by any ADR.

## Context

The agent calls an LLM for reasoning + response generation. We want to:

1. Avoid vendor lock-in (cost optimization, fallback during outages).
2. Have one chokepoint to attach observability (Langfuse traces).
3. Allow developers to test locally with cheaper / free models when iterating.

## Decision

- All LLM calls route through **LiteLLM** (`litellm` Python package).
- Default model: **`claude-sonnet-4-6`** (Anthropic) — best balance of tool-use reliability and cost as of project start.
- Configuration via env var `LITELLM_MODEL` — no code changes to swap providers.
- A single module `apps/backend/src/agent/llm.py` wraps LiteLLM with Langfuse instrumentation. **Nothing else in the codebase may import `litellm` or any provider SDK directly.**

## Why Claude as default

- Tool-use accuracy in ReAct loops is the most critical agent capability for us. Claude Sonnet 4.6 has been the most reliable across our informal evals.
- Streaming + SSE works cleanly.
- Cost per token is competitive with GPT-4o-mini at the quality tier we need.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Anthropic SDK directly | Locks us to Claude; harder to A/B test other providers |
| LangChain `init_chat_model()` | Tightly coupled to LangChain version; LiteLLM is more provider-stable |
| Custom abstraction | Wheel reinvention; LiteLLM already supports 100+ providers |

## Consequences

**Positive:**
- Switching to GPT-4o or Llama 3.1 is a one-env-var change for cost experiments.
- One place to enforce caching, retries, fallback chains, rate limiting.
- One place to ensure every call is traced.

**Negative:**
- LiteLLM occasionally lags behind provider SDKs for cutting-edge features (prompt caching, extended thinking). Mitigation: monitor LiteLLM releases; bypass with a documented exception if a feature is critical and unsupported.

## See also

- LiteLLM: https://docs.litellm.ai
- [ADR 0002 — MCP skills architecture](0002-mcp-skills-architecture.md)
