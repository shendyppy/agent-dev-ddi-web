# Guide — LLM gateway and provider swapping

> **Who this is for**: teammates who have built AI features by importing
> a provider's SDK directly (e.g. `google.genai`, `openai`, Anthropic
> Agent SDK, Google ADK). In *this* repo we don't do that, and this guide
> explains why and how to migrate.
>
> **Prerequisite reading**: [ADR 0003 — LLM via LiteLLM](../adr/0003-llm-via-litellm.md).
> This guide is the operational/hands-on companion to that decision.

---

## 1. The rule, in one sentence

Every LLM call in this repo goes through **one function** in **one file**:
`agent.llm.acompletion(...)` in [`apps/backend/src/agent/llm.py`](../../apps/backend/src/agent/llm.py).

If you ever feel yourself reaching for `import google.genai` /
`import openai` / `import anthropic` / `from google.adk import ...`
inside a feature file — **stop**. You're about to break four things at
once. Read on.

---

## 2. The pattern you're probably used to (and why we don't do it here)

A lot of internal tools today look like this:

```python
# ❌ The pattern we are moving away from
import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
chat = client.chats.create(
    model="gemini-2.5-flash",
    config={"system_instruction": "You are a helpful assistant...",
            "temperature": 0.5},
)
response = chat.send_message(user_query)
print(response.text)
```

This works. It also leaves you with four problems that show up the
moment your feature ships:

| Problem | What it looks like in practice |
|---|---|
| **Vendor lock-in** | Boss says "let's try Claude for this — it's cheaper at our usage". Now you rewrite every call site, every prompt format, every tool spec. |
| **No observability** | A user says "the bot gave me a weird answer yesterday". You have *nothing*. No trace, no input, no output, no token count. You guess. |
| **N places to audit** | Security review asks "where do we send user data to external LLMs?". You grep for the SDK import. Did you find all of them? You hope so. |
| **Inconsistent retry / cache / rate-limit policy** | Feature A retries on 429. Feature B doesn't. Feature C uses streaming. Feature D doesn't. Nobody can reason about cost or reliability anymore. |

Each problem is small alone. The four together is what ADR 0003 was
written to prevent.

---

## 3. The pattern we use instead

One gateway module, one function, one call shape — no matter the provider:

```python
# ✅ The pattern in this repo
from agent.llm import acompletion

response = await acompletion(
    messages=[
        {"role": "system", "content": "You are a helpful assistant..."},
        {"role": "user", "content": user_query},
    ],
    # Optional: pass tools, max_input_tokens, temperature, ...
)
print(response.choices[0].message.content)
```

That's it. Same call shape for Claude, Gemini, GPT-4o, Ollama, anything
LiteLLM supports. The provider is chosen by an env var:

```bash
# .env
LITELLM_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=AIza...
```

…or:

```bash
LITELLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

…or any other provider supported by LiteLLM. **No code change** when you
flip. That is the whole point.

---

## 4. What the gateway buys you (the four problems, solved)

Look at [`agent/llm.py`](../../apps/backend/src/agent/llm.py) — it's
~60 lines. Tiny on purpose. Here's what those 60 lines give you for free
in every feature that uses them:

### 4.1 Provider portability

LiteLLM normalises the call interface. The `messages=[{role, content}]`
shape works across every provider. Tool/function-calling syntax: same.
Streaming: same. JSON mode: same. You write one feature, it runs on any
model.

### 4.2 Observability (Langfuse traces, free)

Notice the `@observe(as_type="generation")` decorator on `acompletion`?
That single line auto-traces every call to Langfuse:

- The full input messages
- The model name
- The output content
- Token usage
- Latency
- Errors

`just trace <session_id>` pretty-prints the whole conversation. When a
user complains about a bad answer, you have *evidence*. Without the
gateway, you'd have to instrument every call site by hand.

### 4.3 One audit point

Security or compliance asks "show me everywhere we send user data to an
LLM". Answer: `agent/llm.py`, line 38. Done.

`grep -r "import litellm\|import openai\|import anthropic\|from google" apps/`
should return **exactly one match** — inside `llm.py`. Any other match
is a violation; fix it before merging.

### 4.4 Future-proof retry / cache / rate-limit / cost ceiling

You want to add an exponential backoff on 429s? You add it once, in
`acompletion`. You want to enforce a per-session cost ceiling? Same.
Want to cache identical prompts in dev to save API spend? Same. Every
feature gets the policy automatically.

That's also why `max_input_tokens` (the "RTK" / Rust Token Killer
pruning) lives in `acompletion` and not in each feature.

---

## 5. Worked example — swapping to Gemini in this repo

This is the actual flip we just did (after retiring the old direct-Gemini
code path; see [ADR 0007](../adr/0007-retire-portrai-cms-agent.md)).

**Step 1 — Get a key**. From Google AI Studio: https://aistudio.google.com/apikey

**Step 2 — Set two env vars in `.env`**:

```bash
LITELLM_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=AIza...your_key...
```

(Note the `gemini/` prefix — that's LiteLLM's provider namespace. Without
it, LiteLLM would think you mean an OpenAI-namespace model called
`gemini-2.5-flash`, which does not exist, and you'd get a 404.)

**Step 3 — Restart `just dev-be`**. That's literally all.

**Step 4 — Verify**. Open the chat UI, ask a question, watch the
response. Or via shell:

```powershell
just dev-be   # in one window

# in another:
curl http://localhost:8000/api/health
# {"status":"healthy"}

# Or do a one-shot call from Python:
cd apps/backend
uv run python -c @'
import asyncio
from agent.llm import acompletion

async def main():
    r = await acompletion(messages=[{"role": "user", "content": "ping in 3 words"}])
    print(r.choices[0].message.content)

asyncio.run(main())
'@
```

If you see a 3-word reply, Gemini is wired correctly through the gateway.

**Step 5 — Want Claude instead?** Change two lines:

```diff
- LITELLM_MODEL=gemini/gemini-2.5-flash
- GEMINI_API_KEY=AIza...
+ LITELLM_MODEL=claude-sonnet-4-6
+ ANTHROPIC_API_KEY=sk-ant-...
```

Restart. Done. No `pip install`, no SDK import change, no feature
rewrite. **That is what the gateway is for.**

---

## 6. Migration recipe — your existing direct-SDK code → the gateway

When you're porting a feature from `google.genai` / `openai` / Agent SDK,
work through this checklist:

### 6.1 Move the prompt out

If your system instruction is a Python string literal:

```python
# ❌ before
self.system_instruction = "You are a helpful AI assistant. ..."
```

…create a file under `prompts/system/<your-feature>.md` with
frontmatter (see [`prompts/AGENTS.md`](../../prompts/AGENTS.md) for the
shape) and load it via the prompt loader:

```python
# ✅ after
from agent import prompts

prompt = prompts.load("your-feature")
system_content = prompt.render(some_var=value)
```

Why: prompts need diff-able history, code review, and eval gating.
Inline strings can't be reviewed by anyone who isn't reading the Python.
See AGENTS.md rule #1.

### 6.2 Move provider config out

```python
# ❌ before
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # ...manual .env parsing...
client = genai.Client(api_key=api_key)
```

`settings.py` already reads `.env` once for the whole app — use it:

```python
# ✅ after — but you usually don't need this at all, because llm.py
# handles credentials internally. You only touch settings when you need
# to branch on which provider is active (rare):
from agent.settings import settings
if settings.litellm_model.startswith("gemini/"):
    ...
```

### 6.3 Replace the call

```python
# ❌ before
chat = client.chats.create(model="gemini-2.5-flash", config={...})
response = chat.send_message(prompt)
text = response.text
```

```python
# ✅ after — one call, provider-agnostic
from agent.llm import acompletion

response = await acompletion(
    messages=[
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_input},
    ],
)
text = response.choices[0].message.content
```

If you need streaming, use `agent.llm.astream` instead. If you need a
provider-specific feature LiteLLM exposes (e.g. tool/function calling,
JSON mode), pass it through `**kwargs` — LiteLLM handles the
translation per provider.

### 6.4 Move retrieval / embeddings out of your feature

If your feature embedded its own docs (like the old
`portrai_cms_agent.py` did with Gemini embeddings):

```python
# ❌ before
self.chunk_embeddings = client.models.embed_content(...)
similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in self.chunk_embeddings]
```

That's a RAG pipeline open-coded inside a feature. We have one already:

- **Indexing** → `agent.indexing.build_index()` (or just `just index`)
- **Search** → the `search_documentation` MCP skill
- **Embedding model** → fastembed, picked in ADR 0004; same model used
  on both sides automatically

So your feature stops doing retrieval at all. It calls the search skill
through the agent loop and gets chunks back. See
[`apps/backend/src/mcp_servers/search_docs/`](../../apps/backend/src/mcp_servers/search_docs/)
for the reference implementation.

### 6.5 Make sure your skill is an MCP server, not an inline tool

If you were building this with Google ADK (or any framework that uses
inline `@tool` decorators), see [ADR 0002 — Skills as MCP servers](../adr/0002-mcp-skills-architecture.md)
and [`apps/backend/src/mcp_servers/AGENTS.md`](../../apps/backend/src/mcp_servers/AGENTS.md).
Every skill is its own folder with `skill.md` + `handler.py` + `server.py`.
Same handler is unit-testable, the same skill works in Claude Desktop /
Cursor, and the protocol enforces a clean I/O boundary.

---

## 7. FAQ

### "But the Google ADK has some Gemini-only feature I need (file API, code execution, …)"

True — LiteLLM doesn't expose every vendor extension. Options, in order
of preference:

1. **Can the feature be expressed as a tool the LLM calls?** Most "extra
   features" (web search, code execution, file upload) can be MCP skills
   in our world. Wrap the capability as a skill; the LLM calls it via
   tool-use. You stay provider-agnostic.
2. **Does LiteLLM support it via `extra_body` / passthrough?** A lot of
   "Gemini-only" features can be triggered by passing provider-specific
   kwargs through `acompletion(**kwargs)`. Check LiteLLM docs for the
   provider.
3. **Genuinely impossible via the gateway?** Write an ADR explaining
   why, propose the targeted exception (e.g. "only the
   `gemini_file_api` MCP server may import `google.genai`, and it's a
   single MCP boundary, not feature code"). Then implement *inside* the
   MCP server boundary, not in feature code.

### "What about model-specific prompt tuning?"

Prompts can declare `model:` in their frontmatter (see
[`prompts/system/main-agent.md`](../../prompts/system/main-agent.md))
for documentation, and you can dispatch to different prompt files based
on `settings.litellm_model` at the call site. But: in practice we keep
*one* prompt that works across providers, and rely on the model's
follow-instruction quality. Swappability is more valuable than per-model
tuning at our scale.

### "I want to track token cost — does LiteLLM handle that?"

Yes. LiteLLM returns token usage in the response, and Langfuse stores
it. `just trace <session_id>` shows cost per call. The "RTK" / token
killer module (`agent.token_killer`) handles pre-call pruning to keep
input under a budget.

### "How do I add a new provider LiteLLM doesn't support?"

Rare. LiteLLM supports ~100 providers. If yours is missing: contribute
upstream (it's small Python), or — short term — write a thin LiteLLM
custom provider in `llm.py`. Don't go around the gateway.

### "I get `ImportError: cannot import name 'get_client' from 'langfuse'`"

`llm.py` uses the Langfuse v3 SDK (`get_client()` +
`update_current_generation()`). If `apps/backend/pyproject.toml` is
pinned to `langfuse>=2.x,<3.0`, the import fails on import-time —
backend won't even start. Fix:

1. Bump the pin in `apps/backend/pyproject.toml` to
   `"langfuse>=3.0,<4.0"`.
2. `cd apps/backend; uv sync`.
3. Smoke-test: `uv run python -c "from langfuse import get_client; print('ok')"`.

The v2→v3 jump is also when Langfuse pivoted to OpenTelemetry-style
instrumentation. The `@observe` decorator API stayed compatible, but the
client-fetching pattern changed from `Langfuse()` constructor to
`get_client()` singleton.

---

## 8. The one-screen recap

- **One file owns LLM access**: `agent/llm.py`.
- **Switch providers** via `.env`: `LITELLM_MODEL=gemini/gemini-2.5-flash` + `GEMINI_API_KEY=...`. Restart. Done.
- **Never** import `openai` / `anthropic` / `google.genai` / `google.adk` in feature code.
- **Prompts** live in `prompts/*.md`, not Python strings.
- **Skills** live as MCP servers in `mcp_servers/`, not as inline tools.
- **Retrieval** uses our shared RAG (Chroma + fastembed via `search_documentation` skill), not per-feature embedding loops.
- **Observability** is automatic when you use the gateway.

Follow the rules, get the benefits. Break a rule, lose them — and the
next person to debug your feature will lose them too.

---

## See also

- [ADR 0002 — Skills as MCP servers](../adr/0002-mcp-skills-architecture.md)
- [ADR 0003 — LLM via LiteLLM](../adr/0003-llm-via-litellm.md)
- [ADR 0004 — RAG stack: ChromaDB + fastembed](../adr/0004-rag-stack.md)
- [ADR 0007 — Retire `portrai_cms_agent.py`](../adr/0007-retire-portrai-cms-agent.md) (the migration this guide grew out of)
- [`apps/backend/src/agent/llm.py`](../../apps/backend/src/agent/llm.py) — the gateway itself, 60 lines, read it
- [`apps/backend/src/mcp_servers/AGENTS.md`](../../apps/backend/src/mcp_servers/AGENTS.md) — how to add an MCP skill
- [LiteLLM provider list](https://docs.litellm.ai/docs/providers) — every supported model + the env vars it expects
