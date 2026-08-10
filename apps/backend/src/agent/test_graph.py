"""Tests for the two guarantees graph.py added in ADR 0009.

Both are pure control-flow concerns — no LLM involved — so they get real unit
tests rather than waiting on the eval runner (evals/run.py is still a
scaffold). The matching eval cases in evals/cases/scope/ cover the parts that
do need a model: whether the *answer* respects the scope and stops searching.
"""

from __future__ import annotations

import json
from typing import ClassVar

import pytest
from langgraph.graph.message import add_messages

from . import graph as graph_mod
from .graph import _drop_unanswered_tool_calls, _route_after_llm, call_tools
from .settings import settings


def _assistant_search_call(call_id: str = "c1", **args) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "search_documentation",
                    "arguments": json.dumps(args),
                },
            }
        ],
    }


@pytest.fixture
def captured_calls(monkeypatch) -> list[tuple[str, dict]]:
    """Record what call_tools dispatches, without spawning an MCP server."""
    calls: list[tuple[str, dict]] = []

    async def fake_call_tool(name: str, arguments: dict):
        calls.append((name, arguments))
        return "{}"

    monkeypatch.setattr(graph_mod.mcp_clients, "call_tool", fake_call_tool)
    return calls


# ─── Scope enforcement ───────────────────────────────────────────────────
# The picked product must constrain retrieval no matter what the model wrote.
# Before this, scope was only a request in the system prompt, so the filter
# held exactly as often as the model felt like cooperating.


@pytest.mark.asyncio
async def test_scope_is_injected_when_model_omits_it(captured_calls):
    state = {
        "messages": [_assistant_search_call(query="how to login")],
        "product_id": "tep-cms",
        "tool_rounds": 0,
    }
    await call_tools(state)
    assert captured_calls[0][1]["product_id"] == "tep-cms"


@pytest.mark.asyncio
async def test_scope_overrides_a_different_product_chosen_by_the_model(captured_calls):
    """The model asking for another product does not widen the scope."""
    state = {
        "messages": [
            _assistant_search_call(query="video call", product_id="dash-participant-saas")
        ],
        "product_id": "tep-cms",
        "tool_rounds": 0,
    }
    await call_tools(state)
    assert captured_calls[0][1]["product_id"] == "tep-cms"


@pytest.mark.asyncio
async def test_no_scope_leaves_model_arguments_untouched(captured_calls):
    """'All products' is an explicit choice — the model keeps control then."""
    state = {
        "messages": [_assistant_search_call(query="compare", product_id="klob")],
        "product_id": None,
        "tool_rounds": 0,
    }
    await call_tools(state)
    assert captured_calls[0][1]["product_id"] == "klob"


@pytest.mark.asyncio
async def test_scope_is_not_injected_into_other_tools(captured_calls):
    """Only the search tool takes a product_id; others must not be rewritten."""
    state = {
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "list_products", "arguments": "{}"},
                    }
                ],
            }
        ],
        "product_id": "tep-cms",
        "tool_rounds": 0,
    }
    await call_tools(state)
    assert "product_id" not in captured_calls[0][1]


@pytest.mark.asyncio
async def test_tool_rounds_increment(captured_calls):
    state = {
        "messages": [_assistant_search_call()],
        "product_id": None,
        "tool_rounds": 2,
    }
    result = await call_tools(state)
    assert result["tool_rounds"] == 3


# ─── History reflects what was dispatched ────────────────────────────────
# The injected scope used to exist only inside call_tools: the transcript kept
# the model's original arguments, so the model read its ignored product_id back
# and nothing outside the function could observe the ADR 0009 guarantee.


@pytest.mark.asyncio
async def test_history_is_corrected_to_the_dispatched_arguments(captured_calls):
    """add_messages replaces by id, so the assistant turn is rewritten in place."""
    request = add_messages([], [_assistant_search_call(query="video call")])[0]
    state = {"messages": [request], "product_id": "tep-cms", "tool_rounds": 0}

    result = await call_tools(state)

    corrected = next(m for m in result["messages"] if m["role"] == "assistant")
    assert corrected["id"] == request.id
    recorded = json.loads(corrected["tool_calls"][0]["function"]["arguments"])
    assert recorded["product_id"] == "tep-cms"
    assert recorded["query"] == "video call"

    merged = add_messages([request], result["messages"])
    assert len(merged) == 2, "correction must replace the turn, not duplicate it"
    assert merged[0].tool_calls[0]["args"]["product_id"] == "tep-cms"


@pytest.mark.asyncio
async def test_history_is_left_alone_when_nothing_was_rewritten(captured_calls):
    """No scope, no rewrite — the turn must not be re-emitted for no reason."""
    request = add_messages([], [_assistant_search_call(query="compare", product_id="klob")])[0]
    state = {"messages": [request], "product_id": None, "tool_rounds": 0}

    result = await call_tools(state)

    assert all(m["role"] == "tool" for m in result["messages"])


# ─── Loop guard ──────────────────────────────────────────────────────────


def test_route_ends_when_model_writes_prose():
    state = {"messages": [{"role": "assistant", "content": "here you go"}], "tool_rounds": 0}
    assert _route_after_llm(state) == "__end__"


def test_route_runs_tools_while_budget_remains():
    state = {"messages": [_assistant_search_call()], "tool_rounds": 0}
    assert _route_after_llm(state) == "tools"


def test_route_forces_final_answer_once_budget_is_spent():
    state = {
        "messages": [_assistant_search_call()],
        "tool_rounds": settings.agent_max_tool_rounds,
    }
    assert _route_after_llm(state) == "final"


def test_budget_is_reached_not_exceeded():
    """One below the cap still runs tools; the cap itself stops the loop."""
    state = {
        "messages": [_assistant_search_call()],
        "tool_rounds": settings.agent_max_tool_rounds - 1,
    }
    assert _route_after_llm(state) == "tools"


# ─── Forced final answer ─────────────────────────────────────────────────
# Observed on 2026-07-27: the guard stopped the loop correctly but the forced
# answer came back empty. The budget is checked after the model has already
# emitted its next tool calls, so the history ended with an unanswered request
# and Gemini replied with no content — the exact failure this node exists to
# prevent.


def test_final_answer_history_drops_the_unanswered_tool_call():
    history = [
        {"role": "user", "content": "q"},
        _assistant_search_call("c1", query="a"),
        {"role": "tool", "tool_call_id": "c1", "content": "result"},
        _assistant_search_call("c2", query="b"),  # never executed
    ]
    trimmed = _drop_unanswered_tool_calls(history)
    assert trimmed[-1]["role"] == "tool"
    assert len(trimmed) == 3


def test_final_answer_history_keeps_answered_calls():
    history = [
        {"role": "user", "content": "q"},
        _assistant_search_call("c1", query="a"),
        {"role": "tool", "tool_call_id": "c1", "content": "result"},
    ]
    assert _drop_unanswered_tool_calls(history) == history


def test_final_answer_history_drops_a_run_of_unanswered_calls():
    history = [
        {"role": "user", "content": "q"},
        _assistant_search_call("c1", query="a"),
        _assistant_search_call("c2", query="b"),
    ]
    assert _drop_unanswered_tool_calls(history) == history[:1]


@pytest.mark.asyncio
async def test_final_answer_withholds_tools_and_appends_the_nudge(monkeypatch):
    """The nudge turn is the mechanism, not an extra.

    Verified against gemini-3.5-flash: `tools=None` alone does not stop a model
    mid-loop (it keeps emitting tool_calls with content=None), and
    `tool_choice="none"` is not honoured for Gemini in the installed LiteLLM.
    Only the explicit instruction turn produces prose, so if this assertion
    ever breaks the guard silently goes back to returning empty answers.
    """
    seen: dict = {}

    async def fake_acompletion(messages, **kwargs):
        seen["messages"] = messages
        seen["tools"] = kwargs.get("tools")

        class _Msg:
            def model_dump(self):
                return {"role": "assistant", "content": "done"}

        class _Resp:
            choices: ClassVar = [type("C", (), {"message": _Msg()})()]

        return _Resp()

    monkeypatch.setattr(graph_mod.llm, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        graph_mod.mcp_clients,
        "discover_all_tools",
        lambda: (_ for _ in ()).throw(
            AssertionError("final_answer must not fetch the tool catalogue")
        ),
    )

    await graph_mod.final_answer(
        {
            "messages": [
                {"role": "user", "content": "q"},
                _assistant_search_call("c1", query="a"),
                {"role": "tool", "tool_call_id": "c1", "content": "result"},
                _assistant_search_call("c2", query="b"),  # refused by the guard
            ],
            "product_id": None,
            "tool_rounds": settings.agent_max_tool_rounds,
        }
    )

    assert seen["tools"] is None
    last = seen["messages"][-1]
    assert last["role"] == "user"
    assert "Stop searching" in last["content"]
    # The refused call must not be sent along with it.
    assert not any(m.get("tool_calls") for m in seen["messages"][-2:])
