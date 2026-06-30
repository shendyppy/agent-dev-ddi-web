"""LangGraph state machine — the agent's main control loop.

This is the orchestrator: it owns the loop ``user → LLM → (maybe tool) →
LLM → … → done``. Everything else (LLM client, tools, prompts) is wired in
from sibling modules so this file stays small and reads top-to-bottom.

Why LangGraph and not "just a while loop"
-----------------------------------------

A while loop would work — the loop here is genuinely "ask the LLM, if it
asked for a tool then run it, otherwise stop". LangGraph buys us three
things that justify the dependency:

1. **State accumulation with merge semantics** — ``add_messages`` appends
   new messages without us having to do the bookkeeping.
2. **Streaming via ``astream``** — every state transition becomes a yielded
   event, which is how ``server.py`` feeds the SSE endpoint.
3. **Conditional edges as named functions** — future routing (e.g. "if the
   answer needs visual evidence, force a screenshot first") slots in
   without touching the body of ``call_llm``.

If those three benefits ever stop earning their keep, ripping LangGraph out
in favour of a hand-written loop is a localised change to this file.

How to extend
-------------

- **Add a new node** (e.g. "rerank retrieved chunks before answering") →
  define an async function with the ``AgentState → dict`` shape and add it
  with ``graph.add_node(name, fn)`` + edges in :func:`build_graph`.
- **Change routing logic** → edit :func:`_route_after_llm` rather than
  threading a flag through ``AgentState``.
- **New state field** → add it to :class:`AgentState` and any node that
  needs it can read/write it through the returned dict.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from . import llm, mcp_clients, prompts
from .settings import REPO_ROOT, settings

# ─── State shape ─────────────────────────────────────────────────────────


class AgentState(TypedDict):
    """The data that flows through the graph on every step.

    ``messages`` uses LangGraph's ``add_messages`` reducer: when a node
    returns ``{"messages": [...]}``, those messages are *appended* rather
    than overwriting the list. That is how the conversation grows across
    LLM-then-tool-then-LLM hops without manual state-stitching.

    ``session_id`` is propagated unchanged for trace correlation in
    Langfuse — every span produced during this graph run shares the id.
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    session_id: str
    # Optional product the user picked in the UI. When set, the system prompt
    # nudges the agent to scope retrieval to this product (soft scope — the
    # agent may still broaden when a question spans products). No reducer: it
    # is set once in the initial state and carried unchanged through the run.
    product_id: str | None


# ─── System prompt assembly ──────────────────────────────────────────────


def _load_product_catalog_snapshot() -> str:
    """Read ``docs/product-catalog.md`` and return its body.

    The system prompt for the main agent embeds this snapshot so the LLM
    can answer "what products do we have?" without a tool call when the
    catalog is small. The authoritative live answer comes from the
    ``list_products`` skill — that's why the prompt also tells the LLM
    "use ``list_products`` for the live version".

    Empty string on any failure: a missing or unreadable catalog should
    not crash a request; the LLM will just have less context.
    """
    catalog = REPO_ROOT / "docs" / "product-catalog.md"
    try:
        return catalog.read_text(encoding="utf-8")
    except OSError:
        return ""


def _product_scope_text(product_id: str | None) -> str:
    """Render the optional "current focus" block injected into the prompt.

    Empty string when no product is selected (the placeholder then renders to
    nothing). When a product is picked in the UI, this tells the agent to scope
    ``search_documentation`` to that product by default — soft scope, so it may
    still broaden for cross-product questions.
    """
    if not product_id:
        return ""
    return (
        "## Current focus\n\n"
        f"The user has selected the product `{product_id}` as their current focus, so "
        f"every question is about THIS product unless they explicitly name another. "
        "Do NOT ask the user which product they mean — they have already told you. "
        f'Call `search_documentation` with `product_id="{product_id}"` by default so '
        "answers stay within this product's documentation. Only omit `product_id` "
        "(searching all products) when the question clearly spans products or asks "
        "to compare them.\n"
    )


async def _system_message(product_id: str | None = None) -> dict[str, Any]:
    """Build the system message that pins the agent's role.

    Loads ``prompts/system/main-agent.md`` (which lives outside Python per
    AGENTS.md rule 1: "Prompts are code, in ``prompts/``") and fills in:

    - ``{{current_date}}`` — today's date so the model does not anchor on
      its training cutoff.
    - ``{{product_catalog}}`` — the markdown of the catalog as context.
    - ``{{product_scope}}`` — the optional "current focus" block (see
      :func:`_product_scope_text`).

    Add new placeholders by editing the prompt and passing the new key
    here. The renderer raises if anything is missing, so omissions surface
    loudly instead of silently dropping context.
    """
    prompt = prompts.load("main-agent")
    rendered = prompt.render(
        product_catalog=_load_product_catalog_snapshot(),
        current_date=date.today().isoformat(),
        product_scope=_product_scope_text(product_id),
    )
    return {"role": "system", "content": rendered}


# ─── LangChain ↔ OpenAI message bridge ───────────────────────────────────
#
# LangGraph's ``add_messages`` reducer wraps any dict appended to the state
# as a LangChain ``BaseMessage`` subclass (HumanMessage, AIMessage, …). That
# gives us de-dupe + id assignment for free, but LiteLLM downstream expects
# OpenAI-shape dicts (``message.get("role")``). The two formats also disagree
# on the field name — LangChain calls it ``type`` (human/ai/system/tool),
# OpenAI calls it ``role`` (user/assistant/system/tool). We bridge once,
# at every boundary that crosses from "graph state" → "LiteLLM" or
# "graph state" → "route decision".

_LC_TYPE_TO_OPENAI_ROLE = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
}


def _tool_call_to_openai(tc: Any) -> dict[str, Any]:
    """Normalise a single tool call to OpenAI shape.

    OpenAI/LiteLLM expect ``{id, type: "function", function: {name,
    arguments}}`` where ``arguments`` is a JSON-encoded *string*. LangChain's
    ``AIMessage.tool_calls`` exposes its own shape instead —
    ``{name, args, id, type: "tool_call"}`` with ``args`` as a *dict*. Because
    ``add_messages`` re-parses every message into an ``AIMessage``, the tool
    calls we read back on the next turn are in LangChain shape, so we must
    convert them or both :func:`call_tools` (reads ``function.name``) and the
    LiteLLM round-trip (matches the tool response by id) break.

    A tool call already carrying a ``function`` key is left untouched.
    """
    if not isinstance(tc, dict):
        tc = {
            "id": getattr(tc, "id", None),
            "name": getattr(tc, "name", None),
            "args": getattr(tc, "args", None),
            "function": getattr(tc, "function", None),
        }
    if isinstance(tc.get("function"), dict):
        return tc
    args = tc.get("args", {})
    arguments = args if isinstance(args, str) else json.dumps(args or {})
    return {
        "id": tc.get("id"),
        "type": "function",
        "function": {"name": tc.get("name", ""), "arguments": arguments},
    }


def _to_openai_dict(m: Any) -> dict[str, Any]:
    """Coerce a LangChain ``BaseMessage`` (or plain dict) → OpenAI-shape dict."""
    if isinstance(m, dict):
        return m
    role = _LC_TYPE_TO_OPENAI_ROLE.get(getattr(m, "type", ""), getattr(m, "type", "user"))
    d: dict[str, Any] = {"role": role, "content": getattr(m, "content", "") or ""}
    if tcs := getattr(m, "tool_calls", None):
        d["tool_calls"] = [_tool_call_to_openai(tc) for tc in tcs]
    if tcid := getattr(m, "tool_call_id", None):
        d["tool_call_id"] = tcid
    if name := getattr(m, "name", None):
        d["name"] = name
    return d


# ─── Graph nodes ─────────────────────────────────────────────────────────


async def call_llm(state: AgentState) -> dict[str, Any]:
    """Ask the LLM for the next step.

    Returns a dict with one new message — whatever the model produced. If
    the model emitted ``tool_calls``, the conditional edge below will
    route to :func:`call_tools`. Otherwise the graph terminates.

    Tool catalogue discovery is cached after the first call (see
    :func:`mcp_clients.discover_all_tools`), so this stays fast on
    subsequent turns.
    """
    tools = await mcp_clients.discover_all_tools()
    messages = [
        await _system_message(state.get("product_id")),
        *(_to_openai_dict(m) for m in state["messages"]),
    ]
    response = await llm.acompletion(messages, tools=tools or None)
    msg = response.choices[0].message
    # LiteLLM returns provider-specific message objects; pydantic dump
    # normalises them to a plain dict that LangGraph's reducer expects.
    return {"messages": [msg.model_dump() if hasattr(msg, "model_dump") else dict(msg)]}


async def call_tools(state: AgentState) -> dict[str, Any]:
    """Run every tool the LLM asked for and feed results back as messages.

    Contract with OpenAI/Anthropic chat protocols:

    - The assistant message that requested the tool stays in the history.
    - For every requested tool call we append a ``role="tool"`` message
      with the matching ``tool_call_id`` and the textual result.
    - The graph loops back to ``call_llm`` so the model can incorporate
      the tool results and either ask for another tool or produce the
      final answer.

    A bad tool name or a tool crash is *not* fatal: we feed the error
    string back as the tool result and let the model self-correct on the
    next turn. This is the standard ReAct-style recovery pattern.
    """
    last = _to_openai_dict(state["messages"][-1]) if state["messages"] else {}
    tool_calls = last.get("tool_calls")
    if not tool_calls:
        # Defensive: the conditional edge should have prevented this. If
        # we get here, treat it as "no work to do" so the graph still
        # closes cleanly instead of hanging.
        return {"messages": []}

    tool_messages: list[dict[str, Any]] = []
    for tc in tool_calls:
        # Tool calls come in OpenAI shape: {id, type, function: {name, arguments}}.
        # ``arguments`` is a JSON-encoded string per the spec.
        tc_id = tc.get("id")
        fn = tc.get("function", {})
        name = fn.get("name", "")
        raw_args = fn.get("arguments", "{}")
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except json.JSONDecodeError as exc:
            arguments = {}
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": f"error: tool arguments were not valid JSON: {exc}",
                }
            )
            continue

        try:
            result = await mcp_clients.call_tool(name, arguments)
            content = result if isinstance(result, str) else json.dumps(result, default=str)
        except KeyError as exc:
            # Unknown tool — surface as a recoverable error so the LLM
            # picks a real tool on the next loop.
            content = f"error: {exc}"
        except Exception as exc:  # noqa: BLE001 — same rationale as above
            content = f"error: tool {name!r} raised {type(exc).__name__}: {exc}"

        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "name": name,
                "content": content,
            }
        )

    return {"messages": tool_messages}


# ─── Routing ─────────────────────────────────────────────────────────────


def _route_after_llm(state: AgentState) -> str:
    """Decide what happens after :func:`call_llm` produces a message.

    If the model asked for at least one tool → go run the tools.
    Otherwise → we're done, end the graph.
    """
    last = _to_openai_dict(state["messages"][-1]) if state["messages"] else {}
    if last.get("tool_calls"):
        return "tools"
    return END


# ─── Graph construction ──────────────────────────────────────────────────


def build_graph() -> Any:
    """Wire the nodes and edges that form the agent loop.

    Visual representation::

        (start) ── llm ──▶ (tool_calls?) ──yes──▶ tools ──▶ llm ──▶ ...
                              └──no──▶ END

    Built once at import time via :func:`get_graph` so repeated requests
    don't pay the construction cost.
    """
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _route_after_llm, {"tools": "tools", END: END})
    # After running tools we always loop back to the LLM — it needs to
    # see the tool results before deciding what to do next (call another
    # tool, or write the final answer).
    graph.add_edge("tools", "llm")
    return graph.compile()


_compiled: Any | None = None


def get_graph() -> Any:
    """Lazy singleton — compile the graph on first use, reuse after.

    Keeps imports cheap (no work at import time) and avoids re-compiling
    on every chat request.
    """
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


__all__ = ["AgentState", "build_graph", "get_graph"]


# Touch ``settings`` so the linter doesn't flag it as unused while wiring
# is in progress. Real settings access happens via the modules above.
_ = settings.litellm_model
