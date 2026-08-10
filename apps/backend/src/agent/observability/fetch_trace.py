"""Pretty-print a Langfuse trace by session id.

    uv run python -m agent.observability.fetch_trace <session_id>

This is step 1 of the "debug a bad RAG answer" flow in CLAUDE.md, and step 2
of that flow is the reason this renders the way it does: *"inspect what
``search_documentation`` returned to the LLM"*. A raw trace dump buries that —
the tool result is one entry inside the message array of the *next* generation,
several hundred lines of JSON down. So the renderer pulls tool results out and
prints them as their own section, in order, before the answer they produced.

That framing is what makes the retrieval-vs-generation split decidable at a
glance: if the chunks printed under RETRIEVED are wrong, the bug is in indexing
or the embedding query; if they are right and the answer still is not, the bug
is in the prompt. Those two paths have completely different fixes.

The session id is the one the ``done`` SSE event returns to the browser (see
``agent.server``) and the one carried unchanged through ``AgentState`` — so a
user can report "session abc123 gave me a wrong answer" and land here directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from langfuse import Langfuse

from ..settings import settings

# Long tool results are the norm — a single search_documentation reply carries
# several document chunks. Truncate by default so one command stays readable,
# and let --full opt into everything when a specific chunk is under suspicion.
DEFAULT_MAX_CHARS = 1200


def _client() -> Langfuse:
    """Build a read client, or exit with the fix rather than a stack trace.

    Deliberately not reusing the client ``agent.llm`` constructs at import
    time: that one is configured for writing and is created with
    ``tracing_enabled=False`` when keys are absent, which would turn a missing
    credential into an empty result set here instead of an error.
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        sys.exit(
            "[trace] Langfuse credentials missing — set LANGFUSE_PUBLIC_KEY and "
            "LANGFUSE_SECRET_KEY in .env. Without them the agent runs fine but "
            "writes no traces, so there is nothing to fetch."
        )
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def _clip(text: str, max_chars: int | None) -> str:
    if max_chars is None or len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n    … [{len(text) - max_chars} more chars — rerun with --full]"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _tool_results(generation_input: Any) -> list[dict[str, Any]]:
    """Tool replies present in a generation's input message list.

    ``agent.llm`` records ``input=messages`` verbatim, so these are the
    OpenAI-shaped dicts the graph assembled — ``role="tool"`` entries are
    exactly what the MCP servers handed back on the previous hop.
    """
    if not isinstance(generation_input, list):
        return []
    return [msg for msg in generation_input if isinstance(msg, dict) and msg.get("role") == "tool"]


def _requested_tool_calls(output: Any) -> list[dict[str, Any]]:
    """Tool calls the model asked for, dug out of a recorded LiteLLM response."""
    if not isinstance(output, dict):
        return []
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return []
    calls = message.get("tool_calls")
    return calls if isinstance(calls, list) else []


def _answer_text(output: Any) -> str:
    if not isinstance(output, dict):
        return _as_text(output)
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        return _as_text(output)
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    return _as_text(output)


def render_trace(trace: Any, *, max_chars: int | None) -> None:
    print(f"\n{'=' * 78}")
    print(f"trace   {trace.id}")
    print(f"session {trace.session_id or '—'}    user {trace.user_id or 'anonymous'}")
    print(f"start   {trace.timestamp}    latency {trace.latency or 0:.2f}s")
    if trace.total_cost:
        print(f"cost    ${trace.total_cost:.6f}")
    print(f"url     {trace.html_path or '—'}")
    print("=" * 78)

    observations = sorted(trace.observations or [], key=lambda o: o.start_time)
    if not observations:
        print("\n(no observations — the run failed before reaching the LLM)")
        return

    for index, obs in enumerate(observations, start=1):
        latency = f"{obs.latency:.2f}s" if obs.latency else "—"
        print(f"\n── [{index}] {obs.type} · {obs.name or '—'} · {obs.model or '—'} · {latency}")
        if obs.level and obs.level != "DEFAULT":
            print(f"   level: {obs.level} {obs.status_message or ''}".rstrip())

        for result in _tool_results(obs.input):
            print(f"\n   RETRIEVED ← tool_call_id={result.get('tool_call_id', '?')}")
            print(f"   {_clip(_as_text(result.get('content')), max_chars)}")

        calls = _requested_tool_calls(obs.output)
        for call in calls:
            function = call.get("function", {}) if isinstance(call, dict) else {}
            print(f"\n   CALLS → {function.get('name', '?')}({function.get('arguments', '')})")

        answer = _answer_text(obs.output).strip()
        if answer and not calls:
            print(f"\n   ANSWER\n   {_clip(answer, max_chars)}")

    if trace.scores:
        print(f"\nscores: {[(s.name, s.value) for s in trace.scores]}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pretty-print the Langfuse trace(s) for a chat session."
    )
    parser.add_argument("session_id", help="Session id from the chat UI's `done` SSE event.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Do not truncate tool results or answers.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Dump the raw trace objects instead of the readable rendering.",
    )
    args = parser.parse_args()

    client = _client()
    traces = client.api.trace.list(session_id=args.session_id).data
    if not traces:
        print(
            f"[trace] no traces for session {args.session_id!r} at {settings.langfuse_host}.\n"
            "        Traces are written asynchronously — if the run just finished, retry in a\n"
            "        few seconds. If it never appears, the run happened while Langfuse keys\n"
            "        were unset, or it was served from the offline fallback (which returns\n"
            "        before the generation is recorded — see agent.llm._fake_completion).",
            file=sys.stderr,
        )
        return 1

    # `list` returns summaries; observations only come back on the detail call.
    detailed = [client.api.trace.get(t.id) for t in traces]

    if args.as_json:
        print(json.dumps([t.dict() for t in detailed], indent=2, ensure_ascii=False, default=str))
        return 0

    for trace in sorted(detailed, key=lambda t: t.timestamp):
        render_trace(trace, max_chars=None if args.full else DEFAULT_MAX_CHARS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
