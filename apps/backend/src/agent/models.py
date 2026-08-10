"""The model catalogue the UI picker offers — derived, not hand-written.

Every entry here comes from ``litellm.model_cost``, the registry that ships
inside the LiteLLM package: 2988 models, each carrying its provider, mode,
context window, per-token cost, tool-calling support and deprecation date. No
network call, no API key, no maintenance burden — it updates when the dependency
does.

This module started as a hand-written tuple of six models and that was wrong.
A hardcoded list goes stale silently: a model is retired and the picker keeps
offering it, a better one ships and nobody notices, and the "does it support
tool calling?" question gets answered by whoever last edited the file rather
than by the provider. Deriving it makes the constraint executable.

The filter, and why each clause is there
----------------------------------------

``mode == "chat"``
    The registry also lists embedding, image-generation and audio models. They
    cannot hold a conversation, so they cannot appear in a chat picker.

``supports_function_calling``
    **The hard requirement.** The agent graph must be able to call
    ``search_documentation`` (see ``graph._SCOPED_TOOL``). A model that cannot
    emit tool calls does not answer worse here — it answers from memory, with no
    retrieval at all, which is the exact failure the whole RAG pipeline exists to
    prevent. 1551 of the 2988 entries clear this.

``deprecation_date`` in the past
    71 entries are already retired. Offering them is offering a 404.

**a credential must exist for its provider**
    An option the user cannot authenticate is worse than an absent one: it looks
    available and fails at send time.

:data:`RECOMMENDED` survives as a small pinned list, but it is now a *hint*
about which to choose, not the definition of what exists. An id in it that the
registry does not vouch for simply does not appear.

How to extend
-------------

To suggest a different default set, edit :data:`RECOMMENDED`. To change what
counts as usable, edit :func:`_is_usable` — and note that loosening the
tool-calling clause breaks the agent rather than degrading it.
"""

from __future__ import annotations

import datetime
import os
from functools import lru_cache
from typing import Any

import litellm

from .llm import _provider_of, resolve_api_key
from .settings import settings

# Pinned to the top of the picker. Ordering is the recommendation: the free
# default first, then the one-key-many-vendors route, then direct providers.
# Anything the registry rejects is dropped, so a stale entry here is inert
# rather than a broken option in the UI.
# Two ids in the first draft of this list — `openrouter/deepseek/deepseek-chat`
# and `openrouter/qwen/qwen3-32b` — did not exist. Nothing caught that while the
# catalogue was hand-written; the registry caught it on the first run. That is
# the argument for deriving, in one incident.
RECOMMENDED: tuple[str, ...] = (
    "gemini/gemini-3.6-flash",
    "openrouter/anthropic/claude-sonnet-4",
    "openrouter/deepseek/deepseek-v3.2-exp",
    "openrouter/qwen/qwen3.5-flash-02-23",
    "claude-sonnet-4-6",
    "deepseek/deepseek-chat",
)

# Providers whose credentials we understand well enough to offer. The registry
# lists 100+, but most are enterprise clouds needing multi-part credentials
# (Bedrock: access key + secret + region; Vertex: project + service account)
# that a single API key cannot express — see ADR 0010. Adding one here is only
# safe once resolve_api_key can actually credential it.
SUPPORTED_PROVIDERS: frozenset[str] = frozenset(
    {
        "gemini",
        "anthropic",
        "openai",
        "deepseek",
        "dashscope",
        "openrouter",
        "mistral",
        "groq",
        "xai",
    }
)


def _is_usable(name: str, spec: Any) -> bool:
    """Whether a registry entry can drive this agent at all."""
    if not isinstance(spec, dict):
        return False
    if spec.get("mode") != "chat":
        return False
    if not spec.get("supports_function_calling"):
        return False
    if spec.get("litellm_provider") not in SUPPORTED_PROVIDERS:
        return False
    deprecated = spec.get("deprecation_date")
    if deprecated and str(deprecated) < datetime.date.today().isoformat():
        return False
    return True


def _env_key_for(provider: str) -> str:
    """The variable name that credentials a provider, for the "go get this" hint."""
    return f"{provider.upper()}_API_KEY"


def _label(name: str) -> str:
    """The model's own name, with the provider prefix dropped.

    Deliberately NOT prettified. Title-casing was tried and made things worse:
    ``claude-sonnet-4-6`` became "Claude Sonnet 4 6", ``chatgpt-4o-latest``
    became "Chatgpt 4O Latest", and ``qwen3.5-flash-02-23`` turned into
    something nobody would recognise. These ids are the strings people copy out
    of provider documentation and paste into configs — mangling them costs
    recognition and buys nothing.

    The provider is returned as its own field, so dropping the prefix here loses
    no information.
    """
    return name.split("/")[-1]


def _note(spec: dict[str, Any]) -> str:
    """One line a reader can choose on: context window and rough price.

    Cost is per-token in the registry, which is unreadable at that scale, so it
    is rendered per million — the unit every provider actually prices in.
    """
    parts: list[str] = []
    window = spec.get("max_input_tokens")
    if window:
        parts.append(f"{int(window) // 1000}k context")
    inp = spec.get("input_cost_per_token")
    out = spec.get("output_cost_per_token")
    if inp is not None and out is not None:
        if inp == 0 and out == 0:
            parts.append("free")
        else:
            parts.append(f"${float(inp) * 1e6:.2f}/${float(out) * 1e6:.2f} per 1M in/out")
    return " · ".join(parts) or "chat model with tool calling"


@lru_cache(maxsize=1)
def _usable_models() -> tuple[dict[str, Any], ...]:
    """Every registry entry this agent could drive, recommended ones first.

    Cached: the registry is a module-level dict that does not change while the
    process runs, and scanning ~3000 entries per request would be waste.
    """
    entries: list[dict[str, Any]] = []
    for name, spec in litellm.model_cost.items():
        if not _is_usable(name, spec):
            continue
        provider = str(spec.get("litellm_provider"))
        entries.append(
            {
                "id": name,
                "label": _label(name),
                "provider": provider,
                "note": _note(spec),
                "env_key": _env_key_for(provider),
                "recommended": name in RECOMMENDED,
            }
        )

    order = {name: i for i, name in enumerate(RECOMMENDED)}
    entries.sort(key=lambda e: (order.get(e["id"], len(order)), e["id"]))
    return tuple(entries)


def available(user_key: str | None = None) -> list[dict[str, object]]:
    """The usable catalogue, each entry marked with whether it can run and on whose key.

    ``source`` is the honest part, and it exists because a single boolean was
    quietly wrong. A pasted key belongs to *one* provider, but nothing in it
    reliably says which — so treating "user has a key" as "every model works"
    marked direct-Anthropic available to someone holding an OpenRouter key, and
    they would only find out at send time. Sniffing the prefix (``sk-or-``,
    ``sk-ant-``) was the obvious alternative and was rejected: it is a guess
    about a format the providers can change whenever they like.

    So we report what we actually know:

    - ``server`` — a key is configured on this deployment. Guaranteed to
      authenticate; selectable with no action from the user.
    - ``your-key`` — no server key, but the caller supplied one. Selectable, and
      the UI says it will use *their* key, so a wrong-provider key produces an
      error they can attribute.
    - ``none`` — nothing available. Still listed, disabled, naming the variable
      to set, because "why is this missing?" is a worse question than "how do I
      enable this?".

    Never returns the key itself, only where one came from.
    """
    has_user_key = bool(user_key and user_key.strip())
    out: list[dict[str, object]] = []
    for entry in _usable_models():
        # Resolved WITHOUT the user key on purpose: this asks the narrower
        # question "can the server authenticate this on its own?", which is the
        # only part we can promise.
        if resolve_api_key(str(entry["id"]), None):
            source = "server"
        elif has_user_key:
            source = "your-key"
        else:
            source = "none"
        out.append({**entry, "available": source != "none", "source": source})
    return out


def default_model() -> str:
    """What the picker starts on — whatever the deployment configured."""
    return settings.litellm_model


def is_allowed(model: str) -> bool:
    """Whether a model id may be used for a chat turn.

    The picker is a UI affordance; this is the enforcement. Without it the
    ``X-Model-Id`` header would let any caller point the backend at an arbitrary
    provider using the server's own credentials — the same "a prompt is not an
    access control" reasoning as ADR 0009, applied to a header.

    Checked against the derived set, so it stays in step with what the picker
    offers automatically. The configured default always passes, so a deployment
    can pin a model the registry does not list without being locked out of its
    own chat.
    """
    if not model:
        return False
    if model == settings.litellm_model:
        return True
    return any(entry["id"] == model for entry in _usable_models())


def env_key_present(env_key: str) -> bool:
    """Whether a given provider variable is set in this process. For diagnostics."""
    return bool(os.environ.get(env_key))


__all__ = [
    "RECOMMENDED",
    "available",
    "default_model",
    "env_key_present",
    "is_allowed",
]


# Re-exported so callers that only need provider resolution do not reach into
# agent.llm for it.
provider_of = _provider_of
