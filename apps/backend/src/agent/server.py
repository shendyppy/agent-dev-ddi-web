"""FastAPI orchestrator — the HTTP entry point for the chatbot.

Start with: ``just dev-be`` (which runs ``uvicorn agent.server:app --reload``).

The HTTP surface is intentionally tiny — five endpoints:

- ``GET /``                  → service identification (for humans / health probes).
- ``GET /api/health``        → JSON liveness check (for load balancers).
- ``GET /api/meta``          → service metadata (model label) for the FE header.
- ``GET /api/products``      → product catalogue for the FE picker (scopes chat).
- ``POST /api/chat`` (SSE)   → the chatbot. Streams agent events as they happen.
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
import traceback
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import mcp_clients
from .graph import get_graph
from .settings import settings

app = FastAPI(
    title="Documentation Agent API",
    description="Orchestrator for the Documentation Agent chatbot. See docs/architecture.md.",
    version="0.1.0",
)

# CORS — allow the Astro dev server (and any localhost port, since
# contributors run on whatever's free) to call /api/*. In production we'd
# tighten this to the actual deployed FE origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        f"http://127.0.0.1:{settings.frontend_port}",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# ─── Static endpoints ────────────────────────────────────────────────────


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "doc-agent", "see": "/docs"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/meta")
def meta() -> dict[str, str]:
    """Return the active model label so the FE header reflects reality.

    Single source of truth: ``settings.litellm_model`` is the same value
    the gateway routes through. Swap ``LITELLM_MODEL`` in ``.env`` and the
    FE chip updates on next mount — no second env var to keep in sync.
    """
    return {"model": settings.litellm_model}


@app.get("/api/products")
async def products() -> dict[str, Any]:
    """List the products the agent can answer about, for the FE picker.

    Delegates to the ``list_products`` MCP skill — the exact same source the
    agent itself uses — so the picker and the agent never disagree on what
    exists. The skill reads distinct product metadata from the ChromaDB index,
    so a freshly added doc shows up here after ``just index``.

    On any failure (index not built, skill error) we return an empty list
    rather than erroring, so the UI degrades to "no picker" instead of a
    broken page.
    """
    try:
        raw = await mcp_clients.call_tool("list_products", {})
        return json.loads(raw) if raw else {"products": []}
    except Exception:  # noqa: BLE001 — picker is best-effort, never fatal
        traceback.print_exc()
        return {"products": []}


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
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        yield {
            "event": "error",
            "data": f"{type(exc).__name__}: {exc}",
        }
    finally:
        # ``done`` always fires, even on error, so the FE can release
        # its "busy" UI state and persist the session_id.
        yield {"event": "done", "data": session_id}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    """Stream a chatbot turn over Server-Sent Events.

    The full conversation history (from the FE) seeds the graph; per-turn
    work happens inside :func:`_stream_graph_events`. We do not block on
    the graph here — ``EventSourceResponse`` consumes the async iterator
    lazily so the first byte goes out as soon as the graph yields its
    first event.
    """
    session_id = req.session_id or str(uuid.uuid4())
    initial_state = {
        "messages": [m.model_dump() for m in req.messages],
        "session_id": session_id,
        "product_id": req.product_id,
        # Rounds are counted per turn, not per conversation — each request
        # gets a fresh budget.
        "tool_rounds": 0,
    }
    return EventSourceResponse(_stream_graph_events(initial_state, session_id))
