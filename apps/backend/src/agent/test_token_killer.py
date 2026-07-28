from __future__ import annotations

import pytest

from .token_killer import (
    count_message_tokens,
    count_tokens,
    group_tool_exchanges,
    prune_to_budget,
)


def _tool_exchange(call_id: str, size: int = 1) -> list[dict]:
    """One assistant tool call plus its reply — the pair pruning must not split."""
    return [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "search_documentation", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": call_id, "name": "search_documentation",
         "content": "chunk " * size},
    ]


def _orphan_tool_ids(messages: list[dict]) -> set[str]:
    """tool_call_ids referenced by a tool reply with no requesting assistant."""
    requested = {
        tc["id"]
        for m in messages
        if m.get("role") == "assistant"
        for tc in (m.get("tool_calls") or [])
    }
    return {
        m["tool_call_id"]
        for m in messages
        if m.get("role") == "tool"
    } - requested


def test_count_tokens_basic():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0


def test_count_tokens_fallback_for_unknown_model():
    assert count_tokens("hello", model="some-future-model-vX") > 0


def test_count_message_tokens_sums_roles_and_content():
    msgs = [
        {"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "ping"},
    ]
    total = count_message_tokens(msgs)
    assert total > count_tokens("you are helpful") + count_tokens("ping")


def test_prune_returns_input_when_under_budget():
    msgs = [{"role": "user", "content": "hi"}]
    assert prune_to_budget(msgs, max_tokens=1000) == msgs


def test_prune_drops_oldest_non_system_messages():
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "old question " * 200},
        {"role": "assistant", "content": "old answer " * 200},
        {"role": "user", "content": "recent question"},
        {"role": "assistant", "content": "recent answer"},
    ]
    pruned = prune_to_budget(msgs, max_tokens=80, keep_recent=2)
    assert pruned[0]["role"] == "system"
    assert pruned[-2:] == msgs[-2:]
    assert count_message_tokens(pruned) <= 80


def test_prune_raises_when_protected_slice_too_large():
    msgs = [
        {"role": "system", "content": "huge system " * 500},
        {"role": "user", "content": "tail"},
    ]
    with pytest.raises(ValueError):
        prune_to_budget(msgs, max_tokens=50, keep_recent=1)


def test_prune_with_no_system_message():
    msgs = [
        {"role": "user", "content": "old " * 100},
        {"role": "assistant", "content": "old " * 100},
        {"role": "user", "content": "recent"},
    ]
    pruned = prune_to_budget(msgs, max_tokens=40, keep_recent=1)
    assert pruned[-1] == msgs[-1]
    assert count_message_tokens(pruned) <= 40


# ─── Tool-exchange integrity ─────────────────────────────────────────────
# Pruning a tool-calling conversation message-by-message eventually drops an
# assistant tool_calls message while keeping its tool reply. Providers reject
# that request outright ("unknown tool_call_id"), so it fails the whole turn
# rather than merely losing context. These tests pin the pairing invariant.


def test_group_tool_exchanges_keeps_call_and_reply_together():
    msgs = [{"role": "user", "content": "q"}, *_tool_exchange("call_1")]
    groups = group_tool_exchanges(msgs)
    assert [len(g) for g in groups] == [1, 2]
    assert groups[1][0]["role"] == "assistant"
    assert groups[1][1]["tool_call_id"] == "call_1"


def test_group_tool_exchanges_absorbs_parallel_replies():
    """One assistant message can request several tools; all replies belong to it."""
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "a", "type": "function",
                 "function": {"name": "search_documentation", "arguments": "{}"}},
                {"id": "b", "type": "function",
                 "function": {"name": "list_products", "arguments": "{}"}},
            ],
        },
        {"role": "tool", "tool_call_id": "a", "content": "ra"},
        {"role": "tool", "tool_call_id": "b", "content": "rb"},
    ]
    assert [len(g) for g in group_tool_exchanges(msgs)] == [3]


def test_prune_never_orphans_a_tool_reply():
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "first question"},
        *_tool_exchange("call_old", size=300),
        {"role": "assistant", "content": "old answer " * 200},
        {"role": "user", "content": "second question"},
        *_tool_exchange("call_recent", size=2),
        {"role": "assistant", "content": "recent answer"},
    ]
    pruned = prune_to_budget(msgs, max_tokens=120, keep_recent=2)

    assert count_message_tokens(pruned) <= 120
    assert _orphan_tool_ids(pruned) == set()
    # And the reverse: no assistant tool_calls left without its reply.
    for i, m in enumerate(pruned):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            replies = {n.get("tool_call_id") for n in pruned[i + 1:]}
            assert {tc["id"] for tc in m["tool_calls"]} <= replies


def test_prune_drops_a_pre_orphaned_tool_reply():
    """Input that was already malformed comes back valid, not passed through."""
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "tool", "tool_call_id": "ghost", "content": "stale " * 200},
        {"role": "user", "content": "recent"},
    ]
    pruned = prune_to_budget(msgs, max_tokens=40, keep_recent=1)
    assert all(m.get("tool_call_id") != "ghost" for m in pruned)
