---
name: rag-eval
description: Use when debugging a bad RAG answer, tuning retrieval, or adding regression coverage. Triggers on phrases like "the agent said wrong thing", "retrieval is off", "add eval for X", "why did it miss this doc", "improve recall on Y". Wraps the canonical debug flow from CLAUDE.md (Langfuse trace → search_documentation output → fix indexing or prompt → eval case).
---

# rag-eval

You are the RAG debugger and eval author for this docs chatbot. The corpus lives in [`docs/`](../../../docs), is indexed into ChromaDB by [`apps/backend/src/agent/indexing.py`](../../../apps/backend/src/agent/indexing.py), and is queried by the `search_documentation` MCP skill.

## Triage flow (run in this exact order — do not skip)

Per [`CLAUDE.md`](../../../CLAUDE.md#when-asked-to-debug-a-bad-rag-answer):

1. **Pull the trace from Langfuse**: `just trace <session_id>`. You need the actual messages and tool calls, not the user's paraphrase.
2. **Inspect what `search_documentation` returned**: copy the top-k chunks, their scores, and their source paths. Save them in the conversation context — you will reference them.
3. **Classify the failure**:
   - **Retrieval miss** — the right chunk was not in top-k. Fix indexing (chunk size, source list, embedding query rewrite).
   - **Retrieval hit but generation wrong** — the chunk was returned, but the model ignored it or hallucinated around it. Fix the prompt in [`prompts/`](../../../prompts/) (sharpen "cite the chunk", add few-shot of grounding behaviour).
   - **No-answer case** — the docs genuinely don't cover it. Fix the corpus (add a doc) or fix the refusal prompt to say "I don't know" cleanly.
4. **Reproduce in isolation**: `just mcp-inspect search_docs` — run the same query against the MCP server directly. This separates retrieval bugs from orchestration bugs.
5. **Add an eval case under [`evals/cases/`](../../../evals/cases/)** that captures this regression. The case must fail before your fix and pass after.
6. **Run `just eval`** (or `just eval-fast` while iterating). Confirm the new case passes and no others regress.
7. **Ship**. Reference the eval case ID in the commit message.

## Retrieval diagnostic checklist

When classifying a retrieval miss, walk through:

- **Chunking**: was the answer split across two chunks such that neither alone is sufficient? → larger chunk size or overlap.
- **Embedding query**: is the user's phrasing semantically distant from the doc's phrasing? → query rewrite step or HyDE.
- **Source coverage**: is the relevant doc even indexed? `grep -r <topic> docs/` and check `indexing.py` sources list.
- **Re-ranker absence**: top-1 wrong but top-10 contains it → add a cross-encoder rerank step.
- **Filter/metadata**: is product-scoped filtering kicking in when it shouldn't?
- **Embedding model drift**: model changed since last reindex? `just reindex`.

## Generation diagnostic checklist

When the chunk was returned but the answer was wrong:

- Is the prompt instructing the model to **quote the chunk verbatim** when possible? Add or strengthen.
- Is the prompt's "if you don't know, say so" clause weaker than its "be helpful" clause? Re-balance.
- Did the model see the chunk before or after the user question? Order matters — chunks should be close to the question.
- Are chunk citations attributed (e.g., `[source: docs/foo.md#section]`)? If not, the model has no anchor to ground.

## Eval case format

Mirror existing cases in `evals/cases/`. Minimal shape:

```yaml
id: <skill>_<short-slug>
description: <what regression this catches>
input:
  query: "<user question>"
expected:
  must_cite: ["docs/path/to/relevant.md"]   # retrieval gate
  must_contain: ["<substring the answer must include>"]
  must_not_contain: ["<forbidden hallucination>"]
tags: [rag, <skill>, <product>]
```

If a check needs LLM-as-judge (semantic equivalence, style), add it as an `assertions:` entry that calls the judge runner — do not invent ad-hoc assertion types.

## When to write an ADR

Per [`AGENTS.md`](../../../AGENTS.md#6-architectural-decisions-go-in-docsadr), file an ADR in `docs/adr/` when:

- Swapping embedding model.
- Swapping vector store (e.g., Chroma → Qdrant).
- Adding a rerank stage.
- Changing chunking strategy at corpus level.

Numbered, dated, Context / Decision / Consequences. Do not skip this — future-you needs the *why*.

## Do not

- Do not "fix" RAG by patching the answer in a prompt without a retrieval test backing it. That regresses silently.
- Do not delete or weaken an eval case to make CI pass. Fix the code or fix the case for a real reason and explain in the commit.
- Do not call the embedding model directly anywhere outside `indexing.py` and the search MCP server.
