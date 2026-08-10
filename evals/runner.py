"""Execute one eval case against the real agent graph.

This module is the only place the suite touches ``agent.*``. It replays a
case's turn through the same graph ``POST /api/chat`` uses — same nodes, same
scope injection, same tool-round budget — because an eval that exercises a
parallel code path proves nothing about the code that ships.

``graph.ainvoke`` rather than ``astream``: the suite only cares about the
finished turn, and the final state already carries both the full message list
and ``tool_rounds``, which is exactly the quantity ``_route_after_llm``
budgets. Streaming would mean reassembling state we would then throw away.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from agent import llm, prompts
from agent.graph import _to_openai_dict, get_graph
from agent.settings import settings

from .case import Case
from .checks import Check, RunTrace, ToolInvocation, evaluate, extract_retrieved_sources

VALID_VERDICTS = ("pass", "fail", "partial")


@dataclass
class RubricScore:
    item: str
    verdict: str
    reason: str


@dataclass
class CaseResult:
    case: Case
    trace: RunTrace
    checks: list[Check]
    rubric: list[RubricScore] = field(default_factory=list)
    # Non-None when the judge itself failed. Kept separate from case failure:
    # a judge outage says nothing about the agent, and must not turn a green
    # suite red.
    judge_error: str | None = None
    duration_s: float = 0.0

    @property
    def passed(self) -> bool:
        """Hard assertions only. Rubric verdicts are reported, never fatal."""
        return not any(c.counts_against_the_build for c in self.checks)

    @property
    def skipped_checks(self) -> list[Check]:
        return [c for c in self.checks if c.skipped]

    @property
    def known_gap_checks(self) -> list[Check]:
        return [c for c in self.checks if c.known_gap]

    @property
    def fixed_gaps(self) -> list[Check]:
        """Known gaps that now pass — the marker should come off."""
        return [c for c in self.checks if c.known_gap and c.passed]


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Tool-call arguments arrive as a JSON string from the model."""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_trace(messages: list[Any], tool_rounds: int) -> RunTrace:
    """Reduce a finished message list to the things cases assert about.

    The final answer is the last assistant message carrying prose. Taking the
    *last* rather than the first matters on the loop-guard path: ``final_answer``
    appends one more assistant turn after the budget is spent, and that turn —
    not the empty tool-calling one before it — is what the user reads.
    """
    trace = RunTrace(tool_rounds=tool_rounds)
    seen_sources: set[str] = set()

    for raw in messages:
        msg = _to_openai_dict(raw)
        role = msg.get("role")

        if role == "assistant":
            for call in msg.get("tool_calls") or []:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                trace.tool_calls.append(
                    ToolInvocation(
                        name=function.get("name", ""),
                        arguments=_parse_arguments(function.get("arguments")),
                    )
                )
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                trace.final_answer = content

        elif role == "tool":
            for source in extract_retrieved_sources(msg.get("name", ""), msg.get("content") or ""):
                if source not in seen_sources:
                    seen_sources.add(source)
                    trace.retrieved_sources.append(source)

    return trace


async def _run_graph(case: Case) -> RunTrace:
    initial_state = {
        "messages": [m.model_dump() for m in case.input.messages],
        "session_id": f"eval-{case.name}",
        "product_id": case.input.product_id,
        "tool_rounds": 0,
    }
    # Same backstop server.py applies, for the same reason — see the comment
    # on _stream_graph_events. Diverging here would let a case pass under a
    # limit production does not have.
    config = {"recursion_limit": settings.agent_max_tool_rounds * 2 + 4}

    try:
        final_state = await get_graph().ainvoke(initial_state, config=config)
    except Exception as exc:  # noqa: BLE001 — any failure is a case failure
        return RunTrace(error=f"{type(exc).__name__}: {exc}")

    return build_trace(
        final_state.get("messages") or [],
        final_state.get("tool_rounds", 0),
    )


def parse_rubric_response(raw: str, items: list[str]) -> list[RubricScore]:
    """Turn the judge's reply into scores, tolerating a fenced code block.

    Models wrap JSON in ```json fences often enough that refusing to strip one
    would throw away a perfectly good judgement at the end of an expensive run.
    Anything genuinely unparseable raises, and the caller records it as a judge
    error rather than a case failure.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError(f"judge returned {type(parsed).__name__}, expected a list")

    scores: list[RubricScore] = []
    for index, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            continue
        verdict = str(entry.get("verdict", "")).lower()
        scores.append(
            RubricScore(
                # Fall back to our own item text: judges paraphrase, and a
                # report that shows the paraphrase is harder to diff run over run.
                item=items[index] if index < len(items) else str(entry.get("item", "")),
                verdict=verdict if verdict in VALID_VERDICTS else "fail",
                reason=str(entry.get("reason", "")),
            )
        )
    return scores


async def _judge(case: Case, trace: RunTrace) -> list[RubricScore]:
    prompt = prompts.load("eval-judge").render(
        user_question="\n".join(m.content for m in case.input.messages if m.role == "user"),
        product_scope=case.input.product_id or "(all products)",
        retrieved_sources="\n".join(f"- {s}" for s in trace.retrieved_sources)
        or "(nothing was retrieved)",
        agent_answer=trace.final_answer or "(the agent produced no answer)",
        rubric_items="\n".join(f"{i}. {item}" for i, item in enumerate(case.expected.rubric, 1)),
    )
    response = await llm.acompletion([{"role": "user", "content": prompt}])
    return parse_rubric_response(response.choices[0].message.content or "", case.expected.rubric)


async def run_case(case: Case, *, judge: bool = True, fast: bool = False) -> CaseResult:
    started = time.perf_counter()
    trace = await _run_graph(case)
    result = CaseResult(
        case=case,
        trace=trace,
        checks=evaluate(trace, case.expected, fast=fast, known_gap=case.known_gap),
        duration_s=time.perf_counter() - started,
    )

    # No point paying for a judgement on a turn that never produced an answer.
    if judge and case.expected.rubric and trace.final_answer:
        try:
            result.rubric = await _judge(case, trace)
        except Exception as exc:  # noqa: BLE001 — judging must not fail the suite
            result.judge_error = f"{type(exc).__name__}: {exc}"

    return result
