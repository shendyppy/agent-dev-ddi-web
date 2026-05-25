"""LangGraph state machine for the Documentation Agent.

Skeleton — implements the canonical ReAct-style loop:

    user_message → call_llm → (if tool_call) call_tool → call_llm → ... → response

Tools come from `mcp_clients.discover_all_tools()`. The LLM is invoked
exclusively through `agent.llm.acompletion`.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from . import llm, mcp_clients, prompts
from .settings import settings


class AgentState(TypedDict):
    messages: Annotated[list[dict[str, Any]], add_messages]
    session_id: str


async def _system_message() -> dict[str, Any]:
    prompt = prompts.load("main-agent")
    rendered = prompt.render(
        product_catalog="(catalog snapshot will be injected at runtime)",
        current_date="2026-05-25",
    )
    return {"role": "system", "content": rendered}


async def call_llm(state: AgentState) -> dict[str, Any]:
    tools = await mcp_clients.discover_all_tools()
    messages = [await _system_message(), *state["messages"]]
    response = await llm.acompletion(messages, tools=tools or None)
    msg = response.choices[0].message
    return {"messages": [msg.model_dump() if hasattr(msg, "model_dump") else msg]}


async def call_tools(state: AgentState) -> dict[str, Any]:
    # TODO: dispatch tool_calls in last message to MCP servers via mcp_clients
    return {"messages": []}


def _route_after_llm(state: AgentState) -> str:
    last = state["messages"][-1] if state["messages"] else {}
    if isinstance(last, dict) and last.get("tool_calls"):
        return "tools"
    return END


def build_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _route_after_llm, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


_compiled = None


def get_graph() -> Any:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


__all__ = ["AgentState", "build_graph", "get_graph"]


# Reference settings to satisfy the linter until real wiring lands.
_ = settings.litellm_model
