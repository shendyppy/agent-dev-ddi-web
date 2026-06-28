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


def prune_to_budget(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    model: str = "gpt-4o",
    keep_recent: int = 2,
) -> list[dict[str, Any]]:
    """Drop oldest non-system messages until the total fits within max_tokens.

    Always retains: the leading system message (if any) and the last `keep_recent`
    messages. Raises ValueError if even the protected slice exceeds the budget —
    the caller must then summarise or truncate at the application level.
    """
    if count_message_tokens(messages, model) <= max_tokens:
        return messages

    system_prefix: list[dict[str, Any]] = []
    body = messages
    if messages and messages[0].get("role") == "system":
        system_prefix = [messages[0]]
        body = messages[1:]

    tail = body[-keep_recent:] if keep_recent > 0 else []
    middle = body[: -keep_recent] if keep_recent > 0 else body

    protected = system_prefix + tail
    if count_message_tokens(protected, model) > max_tokens:
        raise ValueError(
            f"Protected slice (system + last {keep_recent}) already exceeds "
            f"max_tokens={max_tokens}; summarise at the application level."
        )

    kept_middle: list[dict[str, Any]] = []
    for msg in reversed(middle):
        candidate = system_prefix + [msg] + kept_middle + tail
        if count_message_tokens(candidate, model) > max_tokens:
            break
        kept_middle.insert(0, msg)

    return system_prefix + kept_middle + tail
