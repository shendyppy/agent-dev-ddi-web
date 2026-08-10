"""What a run produced, and whether it satisfies a case's expectations.

Deliberately free of any ``agent.*`` import. The checks are the part most
likely to be wrong in a way nobody notices — an assertion that silently never
fires looks exactly like an assertion that passes — so they need their own
fast unit tests, and those tests should not need a model, an index, or an MCP
subprocess to run. ``runner.py`` next door owns everything that does.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .case import Expectations, KnownGap


@dataclass
class ToolInvocation:
    name: str
    arguments: dict[str, Any]


@dataclass
class RunTrace:
    """Everything observable about one agent turn."""

    tool_calls: list[ToolInvocation] = field(default_factory=list)
    # `source` values search_documentation actually returned, in order, deduped.
    retrieved_sources: list[str] = field(default_factory=list)
    # Times the tools node ran — the quantity graph._route_after_llm budgets.
    tool_rounds: int = 0
    final_answer: str = ""
    # Set when the graph raised. A case with an error is a failure regardless
    # of what the assertions say, so this is checked first.
    error: str | None = None


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    # A skipped check neither passes nor fails. It exists so a fast run reports
    # "not evaluated" instead of quietly counting as green — the difference
    # between a CI gate and a no-op that always exits 0.
    skipped: bool = False
    # Marked by the case's `known_gap`. Reported honestly, excluded from the
    # pass/fail verdict. See evals.case.KnownGap.
    known_gap: bool = False

    @property
    def counts_against_the_build(self) -> bool:
        return not self.passed and not self.skipped and not self.known_gap


# Assertions whose outcome is decided by the model: which tools it chose to
# call, how many rounds it took, and the words it wrote. Under LLM_FAKE_MODE
# none of those come from a model — `agent.llm._fake_completion` always emits
# one synthetic search_documentation call and renders the answer from the
# retrieved chunks — so evaluating them there measures the fixture, not the
# agent. Everything else (scope injection, retrieval, no crash) is real in
# both modes and stays enforced.
MODEL_DEPENDENT_CHECKS = frozenset(
    {
        "must_call_tool",
        "must_call_tool_in_order",
        "max_tool_rounds",
        "must_contain_any",
        "must_not_contain",
    }
)


def extract_retrieved_sources(tool_name: str, content: str) -> list[str]:
    """Pull `source` paths out of one search_documentation reply.

    The reply is the JSON-serialised ``SearchOutput`` from
    ``mcp_servers/search_docs/handler.py``. Anything unparseable — a tool
    error string, a different tool, a schema change — yields nothing rather
    than raising: a malformed retrieval should fail the retrieval assertion,
    not crash the run before the other checks get to report.
    """
    if tool_name != "search_documentation":
        return []
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []
    sources = []
    for chunk in payload.get("chunks") or []:
        if isinstance(chunk, dict) and isinstance(chunk.get("source"), str):
            sources.append(chunk["source"])
    return sources


def mentions(needle: str, text: str) -> bool:
    """Whether ``text`` contains ``needle`` as its own word, case-insensitively.

    Plain ``in`` is wrong here, and the failure is not theoretical: the Acelents
    case blocklists ``"npm install"`` because the docs use pnpm — but
    ``"npm install" in "pnpm install"`` is True, so a *correct* answer saying
    ``pnpm install`` tripped the blocklist. That case could never have passed.

    Only the leading edge gets a word boundary. Requiring one at the end too
    would break prefix patterns like ``ZEPHYR_SSO_``, which exist precisely to
    catch invented ``ZEPHYR_SSO_ENABLED``-shaped names. Needles starting with a
    non-word character (``![``, ``/screenshots/``) fall back to substring
    matching, since a boundary before ``!`` or ``/`` means nothing.
    """
    escaped = re.escape(needle)
    pattern = rf"\b{escaped}" if needle[:1].isalnum() or needle[:1] == "_" else escaped
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _source_matches(expected: str, retrieved: str) -> bool:
    """Whether a retrieved source satisfies an expected one.

    Suffix/substring rather than equality so a case can name
    ``acelents-doc-context.md`` without pinning the folder layout. Case
    folding because the corpus is authored on Windows and paths come back with
    whatever casing the filesystem handed over.
    """
    return expected.strip().lower() in retrieved.strip().lower()


def _ordered_subsequence(needles: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(any(item == needle for item in it) for needle in needles)


def evaluate(
    trace: RunTrace,
    expected: Expectations,
    *,
    fast: bool = False,
    known_gap: KnownGap | None = None,
) -> list[Check]:
    """Run every hard assertion the case declared.

    Only assertions the case actually declares produce a Check — an empty
    ``must_not_contain`` yields no entry rather than a vacuous pass, so the
    report shows what was really verified instead of padding the count.

    With ``fast=True`` the model-dependent assertions are still listed, but
    marked skipped rather than judged. See :data:`MODEL_DEPENDENT_CHECKS`.
    """
    checks: list[Check] = []
    called = [tc.name for tc in trace.tool_calls]
    answer = trace.final_answer

    if trace.error:
        checks.append(Check("no_error", False, f"graph raised: {trace.error}"))

    if expected.must_call_tool:
        missing = [t for t in expected.must_call_tool if t not in called]
        checks.append(
            Check(
                "must_call_tool",
                not missing,
                f"missing {missing}" if missing else f"called {sorted(set(called))}",
            )
        )
        if expected.must_call_tool_in_order:
            ok = _ordered_subsequence(expected.must_call_tool, called)
            checks.append(
                Check(
                    "must_call_tool_in_order",
                    ok,
                    f"expected order {expected.must_call_tool}, saw {called}",
                )
            )

    for tool, required_args in expected.tool_args_must_include.items():
        calls = [tc for tc in trace.tool_calls if tc.name == tool]
        if not calls:
            checks.append(Check("tool_args_must_include", False, f"{tool} was never called"))
            continue
        violations = [
            f"call {i} had {key}={call.arguments.get(key)!r}, expected {value!r}"
            for i, call in enumerate(calls)
            for key, value in required_args.items()
            if call.arguments.get(key) != value
        ]
        checks.append(
            Check(
                "tool_args_must_include",
                not violations,
                "; ".join(violations) if violations else f"all {len(calls)} {tool} call(s) match",
            )
        )

    if expected.max_tool_rounds is not None:
        ok = trace.tool_rounds <= expected.max_tool_rounds
        checks.append(
            Check(
                "max_tool_rounds",
                ok,
                f"{trace.tool_rounds} round(s), budget {expected.max_tool_rounds}",
            )
        )

    if expected.must_retrieve_any:
        hits = [
            e
            for e in expected.must_retrieve_any
            if any(_source_matches(e, r) for r in trace.retrieved_sources)
        ]
        checks.append(
            Check(
                "must_retrieve_any",
                bool(hits),
                f"matched {hits}"
                if hits
                else f"none of {expected.must_retrieve_any} in {trace.retrieved_sources or '[]'}",
            )
        )

    if expected.must_contain_any:
        hits = [s for s in expected.must_contain_any if mentions(s, answer)]
        checks.append(
            Check(
                "must_contain_any",
                bool(hits),
                f"found {hits}" if hits else f"none of {expected.must_contain_any}",
            )
        )

    if expected.must_not_contain:
        violations = [s for s in expected.must_not_contain if mentions(s, answer)]
        checks.append(
            Check(
                "must_not_contain",
                not violations,
                f"contains {violations}" if violations else "clean",
            )
        )

    if fast:
        checks = [
            Check(c.name, True, "not evaluated in fast mode", skipped=True)
            if c.name in MODEL_DEPENDENT_CHECKS
            else c
            for c in checks
        ]

    if known_gap:
        # Applied to passing checks too, so the report can point out a gap that
        # has been fixed and ask for the marker to come off.
        checks = [
            Check(c.name, c.passed, c.detail, skipped=c.skipped, known_gap=True)
            if c.name in known_gap.checks and not c.skipped
            else c
            for c in checks
        ]

    return checks
