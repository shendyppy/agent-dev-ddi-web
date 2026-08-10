# ADR 0010 — Explicit credential resolution + bring-your-own-key

- **Status**: Accepted
- **Date**: 2026-08-10
- **Amends**: ADR 0003 (LLM via LiteLLM — the gateway now resolves and passes credentials explicitly instead of relying on ambient environment)

## Context

Three findings, measured against the running system on 2026-08-10.

**1. The stated credential contract is not the real one.** `settings.py` opens
with "All env access in the codebase goes through this module. Never read
os.environ directly elsewhere — it makes the contract implicit and untestable."
It then declares `anthropic_api_key`, `gemini_api_key` and `openai_api_key` —
and **none of the three is read anywhere**. `llm.acompletion` never passes an
`api_key`.

Authentication works anyway, by accident of a library side effect: `import
litellm` calls `load_dotenv()`, which walks up from the working directory, finds
the repo-root `.env`, and loads *the whole file* into `os.environ`. Verified
directly — before the import `GEMINI_API_KEY` is absent from `os.environ`, after
it is present, and unrelated entries such as `SUPABASE_URL` are loaded too.

So the module docstring is exactly inverted: env access does **not** go through
settings, it goes through a transitive dependency's import-time behaviour. That
is implicit and untestable, which is the thing the rule exists to prevent. It
also means the backend process holds every secret in `.env` — including the
Supabase service-role key — in its environment, whether or not it needs them.

**2. Switching provider is documented as three options when it is 141.** The
installed LiteLLM exposes 141 providers, including `deepseek`, `dashscope`
(Qwen), `openrouter`, and `ollama`. `.env.example` lists Anthropic, Google and
OpenAI, and `settings.py` hardcodes fields for the same three, so the codebase
reads as if those were the only choices. `litellm.get_llm_provider()` resolves
the provider from the model string for all of them, and
`litellm.acompletion(api_key=...)` is a real named parameter that overrides the
env lookup for any provider — both verified.

**3. One shared key is the actual bottleneck.** The team shares a single
free-tier Gemini key capped at 20 requests per day per model (ADR-adjacent
context: a single agent turn can spend 5+). Everyone contends for the same
budget, and the key sits in a `.env` that every contributor can read.

## Decision

### Credentials resolve in one function, in the gateway

`agent.llm` gains `resolve_api_key(model, user_key=None)` with a fixed order:

1. **User-supplied key** — passed per request (see BYOK below).
2. **`<PROVIDER>_API_KEY`** — provider derived from the model string via
   `litellm.get_llm_provider`. Keeps several providers usable simultaneously,
   which is what makes a runtime model picker possible.
3. **`MODEL_API_KEY`** — generic fallback. Swapping provider becomes two lines
   in `.env` with no vendor-specific variable name to look up.
4. **`None`** — pass nothing and let LiteLLM's own lookup apply.

Layer 4 is what keeps this backwards compatible: today every call resolves to
`None`, LiteLLM does exactly what it does now, and nothing changes until a key
is configured deliberately.

Layers 2–4 are not optional conveniences. Evals and CI run headless with no user
to supply a key, so removing the environment layers would break `just eval`.

The three dead settings fields are deleted; `model_api_key` and `model_api_base`
replace them. `api_base` is separate because a single key cannot describe a
self-hosted or OpenAI-compatible endpoint.

### Users bring their own key, and the server never stores it

The key is held in the browser's `localStorage`, sent per request in the
`X-Model-Api-Key` header, used, and discarded. It is never written to disk,
never persisted server-side, and never placed in a request body.

**Header rather than body, for a structural reason.** `use-chat.saveHistory`
writes request-shaped data into Supabase. Keeping the credential out of the body
means a future refactor cannot sweep it into the history table by accident. The
protection is in the shape of the data, not in remembering to be careful.

Three leak paths are closed explicitly, each with a test that fails if a key
appears:

| Path | Mitigation |
|---|---|
| Langfuse `update_current_generation` | credential never enters the traced payload |
| The raw `f"{type(exc).__name__}: {exc}"` SSE error in `server.py` | redacted before it is emitted |
| Supabase chat history | prevented by the header decision above |

### The model list is curated, not enumerated

`GET /api/models` returns an allowlist, not LiteLLM's 141 providers.
**Tool-calling support is a hard requirement**: the graph must be able to call
`search_documentation`, and a model that cannot do so does not degrade the agent,
it breaks it outright.

OpenRouter is the recommended route for the picker — one key, many models
(`openrouter/anthropic/...`, `openrouter/qwen/...`) — because per-provider keys
would otherwise mean asking each user for several. Direct-provider access is
retained rather than replaced: the free Gemini tier costs nothing and is what
eval and CI use.

## Consequences

**Good**

- The credential path is explicit, in one function, and unit-testable without a
  provider.
- Quota stops being a shared resource; per-user cost attribution comes free.
- No shared provider secret needs to live in a deployed `.env`.
- `settings.py`'s docstring becomes true.

**Costs and risks**

- `localStorage` is readable by any XSS on the page. The main XSS surface is
  LLM-authored markdown, already sanitised by DOMPurify. Accepted knowingly.
- Users re-paste the key on a new browser or profile. Accepted: the alternative
  is encrypting credentials at rest, which needs a key-management story and
  turns a feature into a credential database.
- A single `MODEL_API_KEY` cannot express multi-credential providers (Bedrock:
  access key + secret + region; Vertex: project + location + service account;
  Azure: key + endpoint + version). Layer 2 covers those if they are ever
  needed; layer 3 is for the single-key majority.
- Routing through OpenRouter sends internal documentation content to a third
  party. Their data-policy controls exist but must be configured deliberately —
  this is a decision to take consciously, not a default to inherit.
- Adding a header to the chat request means CORS matters. It already allows any
  header, so nothing changes today, but a future tightening must keep this one.

## Alternatives considered

- **`MODEL_API_KEY` alone, no per-provider layer.** The original proposal. It
  gives the ergonomics but makes the model picker impossible — a runtime picker
  needs several providers credentialed at once. The layered order keeps both.
- **Keep relying on LiteLLM's `load_dotenv()`.** It works, and it is why nothing
  looked broken. Rejected because it is invisible at the call site, loads
  unrelated secrets into the process environment, and cannot express a
  per-request key at all.
- **Store user keys in Supabase, encrypted.** Rejected for now. Doing it
  correctly requires managed key material and rotation; doing it incorrectly
  produces a credential database with a false sense of safety. Re-open if
  re-pasting becomes a real complaint.
- **A server-side shared pool of keys, assigned per user.** Solves quota without
  BYOK, but keeps the secrets on our side and adds an allocation problem.
  Rejected as more machinery for less isolation.
- **Send the key in the request body.** Simpler on the client. Rejected: the body
  is what gets persisted to chat history, so safety would depend on every future
  edit remembering that.
