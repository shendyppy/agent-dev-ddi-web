"""Token counter + context pruner ("Rust Token Killer").

tiktoken is the Rust-backed tokenizer. We use it here for two jobs:

1. Count tokens in a string or a chat-messages list, fast and offline.
2. Prune a chat-messages list so that it fits within a model's context budget,
   while preserving the system prompt and the most recent N turns.

Models that tiktoken does not know natively (Anthropic, Gemini, etc. via LiteLLM)
fall back to the cl100k_base encoding, which is a close-enough approximation
for budget planning. For exact provider-side counts, use the provider's own
counter at the call site; this module is for *pre-call* budget control.
"""

from __future__ import annotations

from typing import Any

import tiktoken

_DEFAULT_ENCODING = "cl100k_base"
_PER_MESSAGE_OVERHEAD = 4
_PER_REPLY_OVERHEAD = 2


def _encoding_for(model: str) -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding(_DEFAULT_ENCODING)


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    return len(_encoding_for(model).encode(text))


def count_message_tokens(messages: list[dict[str, Any]], model: str = "gpt-4o") -> int:
    enc = _encoding_for(model)
    total = 0
    for msg in messages:
        total += _PER_MESSAGE_OVERHEAD
        for value in msg.values():
            if isinstance(value, str):
                total += len(enc.encode(value))
    return total + _PER_REPLY_OVERHEAD


def group_tool_exchanges(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group messages into slices that must survive or be dropped together.

    Tool-calling protocols are not a flat list of independent messages. An
    assistant message carrying ``tool_calls`` and the ``role="tool"`` messages
    answering it form one indivisible exchange: keep the tool replies without
    the assistant that requested them and the provider rejects the request for
    referencing an unknown ``tool_call_id``; keep the assistant without its
    replies and it rejects the unanswered call. Pruning message-by-message will
    eventually split one of those pairs, which is why pruning operates on these
    groups instead.

    Every other message is a group of one. A ``role="tool"`` message with no
    preceding requester (already orphaned before we were called) becomes its
    own group so the caller can drop it rather than pass invalid input along.
    """
    groups: list[list[dict[str, Any]]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        tool_calls = msg.get("tool_calls") if msg.get("role") == "assistant" else None
        if not tool_calls:
            groups.append([msg])
            i += 1
            continue

        expected_ids = {tc.get("id") for tc in tool_calls if isinstance(tc, dict)}
        group = [msg]
        i += 1
        # Absorb the replies to this call. Stop at the first message that is
        # not one of them, so an interleaved turn can't be swallowed.
        while i < len(messages) and messages[i].get("role") == "tool":
            if expected_ids and messages[i].get("tool_call_id") not in expected_ids:
                break
            group.append(messages[i])
            i += 1
        groups.append(group)
    return groups


def _drop_orphan_tool_messages(
    groups: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    """Remove groups that are a lone ``role="tool"`` message.

    Only reachable when the input was already malformed, or when a caller
    sliced the history by hand. Dropping is the right move: an orphan tool
    reply is unusable context that will fail provider validation.
    """
    return [g for g in groups if not (len(g) == 1 and g[0].get("role") == "tool")]


def prune_to_budget(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    model: str = "gpt-4o",
    keep_recent: int = 2,
) -> list[dict[str, Any]]:
    """Drop oldest non-system messages until the total fits within max_tokens.

    Always retains: the leading system message (if any) and the last
    `keep_recent` *exchanges*. An exchange is usually one message, but an
    assistant tool call plus its replies counts as one — see
    :func:`group_tool_exchanges` for why they cannot be split.

    Raises ValueError if even the protected slice exceeds the budget — the
    caller must then summarise or truncate at the application level.
    """
    if count_message_tokens(messages, model) <= max_tokens:
        return messages

    system_prefix: list[dict[str, Any]] = []
    body = messages
    if messages and messages[0].get("role") == "system":
        system_prefix = [messages[0]]
        body = messages[1:]

    groups = _drop_orphan_tool_messages(group_tool_exchanges(body))

    tail_groups = groups[-keep_recent:] if keep_recent > 0 else []
    middle_groups = groups[:-keep_recent] if keep_recent > 0 else groups

    def flatten(gs: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        return [m for g in gs for m in g]

    tail = flatten(tail_groups)
    protected = system_prefix + tail
    if count_message_tokens(protected, model) > max_tokens:
        raise ValueError(
            f"Protected slice (system + last {keep_recent}) already exceeds "
            f"max_tokens={max_tokens}; summarise at the application level."
        )

    kept_middle: list[list[dict[str, Any]]] = []
    for group in reversed(middle_groups):
        candidate = system_prefix + flatten([group, *kept_middle]) + tail
        if count_message_tokens(candidate, model) > max_tokens:
            break
        kept_middle.insert(0, group)

    return system_prefix + flatten(kept_middle) + tail
