from __future__ import annotations

import pytest

from .token_killer import count_message_tokens, count_tokens, prune_to_budget


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
