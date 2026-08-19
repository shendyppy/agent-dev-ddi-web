"""FastAPI orchestrator — the HTTP entry point for the chatbot.

Start with: ``just dev-be`` (which runs ``uvicorn agent.server:app --reload``).

The HTTP surface is intentionally tiny — five endpoints:

- ``GET /``                  → service identification (for humans / health probes).
- ``GET /api/health``        → JSON liveness check (for load balancers).
- ``GET /api/meta``          → service metadata (model label) for the FE header.
- ``GET /api/models``        → curated model catalogue for the FE picker, each
                              entry flagged available/unavailable against the
                              caller's own key (ADR 0010).
- ``GET /api/products``      → product catalogue for the FE picker (scopes chat).
- ``POST /api/chat`` (SSE)   → the chatbot. Streams agent events as they happen.
                              Optional ``X-Model-Id`` and ``X-Model-Api-Key``
                              headers select the model and supply the caller's
                              own credential. Headers, not body fields — see the
                              docstring on :func:`chat`. ``X-Offline-Mode: true``
                              answers from the local index without calling the
                              provider, for this request only.
- ``GET /screenshots/{file}``→ static PNGs captured by the ``capture_screenshot``
                              skill. Mounted from ``settings.screenshot_dir``.
                              The agent embeds these URLs as markdown images in
                              its answers; the FE's ``<img>`` fetches them here.

All real work lives in ``agent.graph`` (LangGraph state machine) which fans
out to ``agent.mcp_clients`` (MCP skill servers) and ``agent.llm`` (LiteLLM
+ Langfuse gateway). This file's only job is the transport layer.

SSE event contract sent on ``/api/chat``
----------------------------------------

Each event is a standard ``text/event-stream`` frame::

    event: <name>
    data: <utf-8 string, JSON when not empty>

    (blank line ends the frame)

Event names emitted:

- ``message``     — JSON of one new message added to the conversation.
                    Shape: ``{role, content, tool_calls?, tool_call_id?, name?}``.
                    The frontend appends these to its message list.
- ``retrieval``   — JSON verdict over the passages the last documentation
                    search returned, produced by ``agent.relevance``.
                    Shape: ``{question, product_id, confidence,
                    chunks: [{source, heading, score, overlap, verdict,
                    excerpt}]}``. Emitted from the ``tools`` node, so it always
                    arrives BEFORE the answer it explains — the FE holds it and
                    attaches it to the next assistant message with content.
                    Rejected passages are included on purpose: seeing a
                    high-scoring chunk thrown out for zero keyword overlap is
                    what makes the ranking legible. Advisory only — it does not
                    change what the model was given.
- ``done``        — terminator. ``data`` is the session_id so the FE can
                    persist it for follow-up turns.
- ``error``       — something blew up inside the graph. ``data`` is a
                    human-readable string. FE shows it as an assistant
                    error bubble.

Adding a new event type? Document it here and update the FE's SSE handler
at the same time. Drift between the two is the most common SSE bug.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import traceback
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import frontmatter
import yaml
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import mcp_clients, models
from .graph import get_graph
from .settings import settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Warm the MCP tool registry before the server accepts any traffic.

    Discovery spawns one subprocess per skill server and asks each for its
    tool list. It used to happen lazily on the first request that needed a
    tool — which meant an early ``GET /api/products`` could arrive while
    ``list_products`` was not registered yet, get a KeyError, and be reported
    to the browser as ``200 {"products": []}``. The frontend cannot tell that
    apart from a genuinely empty catalogue, so the scope gate rendered with no
    products and the conversation could not start.

    Uvicorn only begins listening once lifespan startup returns, so warming
    here removes the window entirely rather than papering over it. A few extra
    seconds of boot is the right trade for never serving a wrong answer.

    A failure here is logged, not raised: the server still starts, and the
    endpoints below report 503 until discovery succeeds.
    """
    try:
        tools = await mcp_clients.discover_all_tools()
        # Catalogue entries are OpenAI-shaped: {"type": "function", "function": {...}}.
        names = sorted(t.get("function", {}).get("name", "?") for t in tools)
        print(f"[server] MCP tools ready: {names}", file=sys.stderr)
    except Exception:  # noqa: BLE001 — startup must not be fatal
        traceback.print_exc()
        print("[server] MCP discovery failed at startup — /api/products will 503", file=sys.stderr)
    yield


app = FastAPI(
    title="Documentation Agent API",
    description="Orchestrator for the Documentation Agent chatbot. See docs/architecture.md.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
# The loopback regex exists because contributors run the dev server on whatever
# port is free. It is a DEV convenience and must not survive into a deployment:
# combined with `allow_credentials=True` it would let any origin the regex
# admits make credentialed calls, and since ADR 0010 those calls can carry a
# user's provider key in `X-Model-Api-Key`.
#
# So the loopback allowance is now conditional rather than unconditional. Set
# CORS_ALLOWED_ORIGINS to the real frontend origin(s) in any environment that is
# not a developer laptop and the wildcard disappears; leave it unset and dev
# keeps working exactly as before.
_cors_origins = settings.cors_allowed_origins_list or [
    f"http://localhost:{settings.frontend_port}",
    f"http://127.0.0.1:{settings.frontend_port}",
]
# Only when no explicit allowlist was configured. `None` disables the regex.
_cors_origin_regex = (
    None if settings.cors_allowed_origins_list else r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$"
)
if not settings.cors_allowed_origins_list:
    print(
        "[server] CORS: no CORS_ALLOWED_ORIGINS set — allowing any loopback origin. "
        "Set it before deploying.",
        file=sys.stderr,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    # Named rather than "*": these are the only headers the API reads, and an
    # explicit list means adding a new one is a decision instead of an accident.
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Model-Id",
        "X-Model-Api-Key",
        "X-Offline-Mode",
    ],
)

# Static screenshots — PNGs produced by the capture_screenshot skill (Playwright)
# land in settings.screenshot_dir and are served here so the browser can fetch
# them via the markdown image URL the agent embeds in its answer. Created on
# startup so a fresh checkout serves an empty dir (404) instead of crashing on
# the mount. See ADR 0008 for why screenshots flow as image URLs, not a new SSE
# event type.
settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/screenshots",
    StaticFiles(directory=str(settings.screenshot_dir)),
    name="screenshots",
)


# ─── Schemas ─────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """One message in the conversation history sent up by the frontend.

    Kept minimal — role + content. The frontend doesn't deal with
    ``tool_calls``/``tool_call_id``; those are emitted by the agent and
    only shown for awareness. On the next turn, the FE replays the user's
    role+content history.
    """

    role: str
    content: str


class ChatRequest(BaseModel):
    """Body of POST /api/chat.

    Send the full prior conversation each turn. We do not persist it
    server-side — the FE owns conversation state. ``session_id`` is
    optional on the first turn; the server will mint one and return it in
    the ``done`` event for the FE to reuse on follow-ups (drives Langfuse
    trace correlation).
    """

    messages: list[ChatMessage]
    session_id: str | None = None
    # Optional product the user selected in the UI picker. When present, the
    # agent scopes its documentation search to this product (soft scope — see
    # graph._product_scope_text). None / absent = search across all products.
    product_id: str | None = None


class KnowledgeBaseRequest(BaseModel):
    """Body of POST /api/knowledge-base."""

    filename: str
    product_id: str
    product_name: str
    content: str
    # Explicit opt-in to replacing a document that already exists. Absent or
    # false means a name collision is refused rather than silently applied:
    # this is the only write path into the corpus, nothing here goes through
    # git, and there is no undo — so an accidental overwrite is unrecoverable.
    # "FAQ" and "faq!!!" both sanitize to faq.md, which makes the collision far
    # more likely than it looks.
    overwrite: bool = False


# A full rebuild currently takes ~60s on this corpus and grows with it. The cap
# is generous enough not to fire in normal use, and exists so a wedged run
# fails the request instead of pinning a threadpool worker indefinitely.
INDEX_TIMEOUT_SECONDS = 600


@app.post("/api/knowledge-base")
def create_knowledge_base(request: KnowledgeBaseRequest) -> dict[str, str]:
    """Save a new knowledge base document to ``docs/knowledge-base``, then reindex."""
    from .settings import REPO_ROOT

    # Sanitize the filename, replace spaces with hyphens, convert to lowercase.
    # This also neutralises path separators and "..", so the result cannot
    # escape kb_dir — they become literal hyphens rather than traversal.
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", request.filename).strip("-").lower()
    if not safe_name:
        safe_name = "untitled"
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    kb_dir = REPO_ROOT / "docs" / "knowledge-base"
    kb_dir.mkdir(parents=True, exist_ok=True)
    file_path = kb_dir / safe_name

    if file_path.exists() and not request.overwrite:
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{safe_name}' already exists. Resend with overwrite=true to replace it, "
                "or choose a different filename."
            ),
        )

    # Frontmatter is serialised by PyYAML, never interpolated into a string.
    # A product name as ordinary as "Klob: Mobile App" produces invalid YAML
    # when pasted raw between the --- fences; safe_dump quotes whatever needs
    # quoting. allow_unicode keeps Indonesian product names readable on disk
    # instead of escaping them to \uXXXX.
    header = yaml.safe_dump(
        {
            "product_id": request.product_id,
            "product_name": request.product_name,
            "status": "active",
        },
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    full_content = f"---\n{header}---\n\n{request.content}"

    # Parse the document back before it touches the corpus. Writing first and
    # discovering the problem at index time is what made one bad document
    # permanent: the file survived the failed subprocess and then broke every
    # later indexing run for everyone. Rejecting here means a malformed
    # document never reaches disk at all.
    try:
        frontmatter.loads(full_content)
    except Exception as exc:  # any parse failure is the caller's 422, not our 500
        raise HTTPException(
            status_code=422,
            detail=f"document is not valid markdown+frontmatter: {type(exc).__name__}: {exc}",
        ) from exc

    file_path.write_text(full_content, encoding="utf-8")

    # Trigger a synchronous index rebuild. stderr is captured rather than
    # discarded so a failure can say what went wrong instead of surfacing as a
    # bare 500 with no diagnostic anywhere. Each failure mode is reported
    # distinctly, and all of them make clear the document *was* saved — the
    # caller should not retype it.
    try:
        subprocess.run(
            ["just", "index"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=INDEX_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=(
                f"'{safe_name}' was saved, but 'just' is not on PATH so it could not be "
                "indexed. Run 'just index' manually to make it searchable."
            ),
        ) from exc
    except subprocess.TimeoutExpired as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=504,
            detail=(
                f"'{safe_name}' was saved, but indexing exceeded {INDEX_TIMEOUT_SECONDS}s "
                "and was abandoned. It is not searchable yet."
            ),
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", "replace").strip()
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=(
                f"'{safe_name}' was saved, but indexing failed: "
                f"{stderr[-500:] or 'no stderr captured'}"
            ),
        ) from exc

    return {"status": "success", "file": safe_name}


# ─── Chat endpoint ───────────────────────────────────────────────────────


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "doc-agent", "see": "/docs"}


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness, plus enough identity to tell *which* service answered.

    ``service`` exists because a bare ``{"status": "healthy"}`` is true of
    every uvicorn app on the machine. When another project held port 8000, a
    curl against /api/health looked entirely healthy — it was simply a
    different program. One field makes "am I talking to doc-agent?" answerable
    in one request instead of by inspecting a 404 that the browser has already
    turned into a CORS message.
    """
    return {"status": "healthy", "service": "doc-agent"}


@app.get("/api/meta")
def meta() -> dict[str, str]:
    """Return the active model label so the FE header reflects reality.

    Single source of truth: ``settings.litellm_model`` is the same value
    the gateway routes through. Swap ``LITELLM_MODEL`` in ``.env`` and the
    FE chip updates on next mount — no second env var to keep in sync.
    """
    return {"model": settings.litellm_model}


@app.get("/api/models")
def list_models(x_model_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    """Models the picker may offer, each flagged with whether it can actually run.

    Availability is resolved through the same credential chain the gateway uses
    (``llm.resolve_api_key``), so an entry marked available here will
    authenticate at send time — rather than being a second guess that drifts
    from the real one.

    The caller's own key is read from the header so the answer reflects *their*
    access: one pasted OpenRouter key lights up every OpenRouter entry at once.
    The key is used for the check and discarded; it is never echoed back, and
    the response carries only booleans and the variable *name* to go and set.
    """
    return {
        "models": models.available(x_model_api_key),
        "default": models.default_model(),
    }


@app.get("/api/products")
async def products() -> dict[str, Any]:
    """List the products the agent can answer about, for the FE picker.

    Delegates to the ``list_products`` MCP skill — the exact same source the
    agent itself uses — so the picker and the agent never disagree on what
    exists. The skill reads distinct product metadata from the ChromaDB index,
    so a freshly added doc shows up here after ``just index``.

    Failure modes are NOT equivalent, and collapsing them was a real bug:

    - The skill ran and found nothing (index not built) → ``{"products": []}``
      with 200. That is a true answer, and the FE shows its "all products"
      escape hatch.
    - The skill could not run (discovery incomplete, server crashed) → **503**.
      This used to return 200 with an empty list, which the browser cannot
      distinguish from the case above: the scope gate rendered with no product
      cards and the user was stuck, permanently, because a 200 gives the client
      no reason to ask again. A 503 says "not now, ask later", which is both
      true and actionable — the FE retries it with backoff.
    """
    try:
        raw = await mcp_clients.call_tool("list_products", {})
    except KeyError as exc:
        # Tool absent from the registry: discovery has not completed or the
        # skill is misregistered. Transient from the caller's point of view.
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=f"product catalogue not ready: {exc}") from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=503, detail=f"product catalogue unavailable: {type(exc).__name__}"
        ) from exc

    return json.loads(raw) if raw else {"products": []}


# ─── The chat endpoint ───────────────────────────────────────────────────


def _format_message_for_wire(msg: Any) -> dict[str, Any]:
    """Reshape one LangGraph message into the FE-facing JSON.

    Messages flowing through the graph come in two shapes depending on
    their origin:

    - Plain dicts (user input we put in, tool results we appended).
    - LiteLLM message objects (assistant outputs) — ``.model_dump()`` was
      already called in graph.py, so they're dicts here too.

    We allowlist the keys we care about so the FE never has to guard
    against provider-specific extras leaking through.
    """
    if not isinstance(msg, dict):
        return {"role": "assistant", "content": str(msg)}

    out: dict[str, Any] = {"role": msg.get("role", "assistant")}
    if "content" in msg and msg["content"] is not None:
        out["content"] = msg["content"]
    if msg.get("tool_calls"):
        out["tool_calls"] = msg["tool_calls"]
    if msg.get("tool_call_id"):
        out["tool_call_id"] = msg["tool_call_id"]
    if msg.get("name"):
        out["name"] = msg["name"]
    return out


# Shapes that are credentials wherever they appear. Redacting on shape as well
# as on the exact known value matters because the caller's key is not the only
# one that can reach an error string: a provider SDK can just as easily echo the
# SERVER's key back, and server.py has no list of those to compare against —
# they live in os.environ under 141 possible names.
#
# Deliberately narrow patterns. A greedy "anything long and random" rule would
# scrub session ids and file hashes out of error messages and make real failures
# undebuggable, which trades one blind spot for another.
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),  # OpenAI, DeepSeek, OpenRouter, Anthropic
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}"),  # Google / Gemini
    re.compile(r"\b(?:gsk|xai|pplx)-[A-Za-z0-9_-]{16,}"),  # Groq, xAI, Perplexity
    # `Bearer <token>` on its own, because the token is separated from the
    # header name by the scheme word — `Authorization:\s*\S{12,}` matches
    # "Bearer" itself and stops, leaving the credential in place.
    re.compile(r"(?i)\bBearer\s+\S{12,}"),
    re.compile(r"(?i)\b(?:api[-_]?key|authorization)\s*[=:]\s*\S{12,}"),
)

_REDACTED = "***redacted***"


def _redact(text: str, secret: str | None) -> str:
    """Strip credentials out of text before it leaves the process.

    One of the three leak paths ADR 0010 names. Provider SDK errors are built by
    code we do not control and have been known to echo request material back;
    this endpoint forwards those strings verbatim to the browser, so the
    redaction belongs here, at the boundary, rather than being assumed upstream.

    Two passes, because they cover different failures: the exact value catches
    the caller's key even in an unusual format, and the patterns catch keys this
    function was never told about — including the deployment's own.

    Cheap and unconditional on purpose: a missing redaction is a leaked key,
    while a needless one costs a string scan.
    """
    if secret and len(secret) >= 8:
        text = text.replace(secret, _REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


async def _stream_graph_events(
    initial_state: dict[str, Any],
    session_id: str,
) -> AsyncIterator[dict[str, str]]:
    """Run the graph and yield SSE events as new messages are produced.

    LangGraph's ``astream`` (default ``stream_mode="updates"``) yields one
    dict per node execution shaped ``{node_name: {messages: [...new]}}``.
    We flatten that to one ``message`` SSE event per new message.

    Any exception is reported back as an ``error`` event rather than
    propagated — the FE renders it inline so the user sees what broke
    instead of a silent connection drop.
    """
    graph = get_graph()
    # Belt and braces. The real stop is the tool-round budget in graph's
    # _route_after_llm; this is the backstop for any path that bypasses it.
    # LangGraph counts *supersteps*, and one round costs two (llm + tools),
    # so the limit has to be at least double the round budget — plus headroom
    # for the entry hop and the forced final answer. Passing it explicitly
    # also puts the number in the code instead of silently inheriting
    # LangGraph's default of 25.
    config = {"recursion_limit": settings.agent_max_tool_rounds * 2 + 4}
    try:
        async for event in graph.astream(initial_state, config=config):
            for _node_name, node_output in event.items():
                new_messages = (node_output or {}).get("messages") or []
                for msg in new_messages:
                    yield {
                        "event": "message",
                        "data": json.dumps(_format_message_for_wire(msg)),
                    }
                # Emitted after the tool messages of the same node so the FE has
                # already drawn its "found in the docs" chip by the time the
                # evidence for it arrives.
                if retrieval := (node_output or {}).get("retrieval"):
                    yield {"event": "retrieval", "data": json.dumps(retrieval)}
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        yield {
            "event": "error",
            "data": _redact(f"{type(exc).__name__}: {exc}", initial_state.get("api_key")),
        }
    finally:
        # ``done`` always fires, even on error, so the FE can release
        # its "busy" UI state and persist the session_id.
        yield {"event": "done", "data": session_id}


@app.post("/api/chat")
async def chat(
    req: ChatRequest,
    x_model_id: str | None = Header(default=None),
    x_model_api_key: str | None = Header(default=None),
    x_offline_mode: str | None = Header(default=None),
) -> EventSourceResponse:
    """Stream a chatbot turn over Server-Sent Events.

    The full conversation history (from the FE) seeds the graph; per-turn
    work happens inside :func:`_stream_graph_events`. We do not block on
    the graph here — ``EventSourceResponse`` consumes the async iterator
    lazily so the first byte goes out as soon as the graph yields its
    first event.

    **Model and credential arrive as headers, not body fields** (ADR 0010). The
    frontend persists request-shaped data to Supabase chat history, so keeping
    the key out of the body means a future refactor cannot sweep it into that
    table by accident. The protection is in the shape of the data rather than in
    remembering to be careful. Both are optional; absent means "use whatever the
    deployment configured", which is the pre-BYOK behaviour exactly.
    """
    session_id = req.session_id or str(uuid.uuid4())

    # The picker is a UI affordance; this is the enforcement. Without it the
    # header would let any caller aim the backend at an arbitrary provider using
    # the server's own credentials.
    if x_model_id and not models.is_allowed(x_model_id):
        raise HTTPException(status_code=400, detail=f"model {x_model_id!r} is not allowed")

    initial_state = {
        "messages": [m.model_dump() for m in req.messages],
        "session_id": session_id,
        "product_id": req.product_id,
        # Rounds are counted per turn, not per conversation — each request
        # gets a fresh budget.
        "tool_rounds": 0,
        "retrieval": None,
        "model": x_model_id,
        "api_key": x_model_api_key,
        # Explicit "true" only. Header values are strings, so a truthiness test
        # would read "false" and "0" as on — the two things someone sending this
        # off most plausibly writes.
        "offline": (x_offline_mode or "").strip().lower() == "true",
    }
    return EventSourceResponse(_stream_graph_events(initial_state, session_id))
