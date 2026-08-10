"""Console summary and on-disk artifacts for an eval run.

Two audiences, two formats. The console output is for the person who just
changed a prompt and wants to know in five seconds whether they broke
something — so failures print their reason inline and passes stay one line.
The JSON under ``evals/.runs/`` is for comparing runs to each other, which is
the only way to tell "retrieval got better" from "the model had a good day".
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .runner import CaseResult

RUNS_DIR = Path(__file__).parent / ".runs"

PASS = "PASS"
FAIL = "FAIL"


def _verdict_counts(results: list[CaseResult]) -> dict[str, int]:
    counts = {"pass": 0, "partial": 0, "fail": 0}
    for result in results:
        for score in result.rubric:
            counts[score.verdict] = counts.get(score.verdict, 0) + 1
    return counts


def print_summary(results: list[CaseResult], *, fast: bool) -> None:
    print()
    if fast:
        print(
            "MODE: fast — LLM_FAKE_MODE is on, so no model was called.\n"
            "      Enforced: the graph runs, scope injection holds, retrieval "
            "returns sources.\n"
            "      NOT enforced: tool choice, round count, and everything about "
            "the answer text —\n"
            "      those are marked 'skipped' below. A green fast run is not "
            "evidence that a\n"
            "      prompt change is safe; run `just eval` for that."
        )
        print()

    for result in results:
        status = PASS if result.passed else FAIL
        skipped = result.skipped_checks
        suffix = f", {len(skipped)} check(s) skipped" if skipped else ""
        print(
            f"[{status}] {result.case.group}/{result.case.name}  "
            f"({result.duration_s:.1f}s, {result.trace.tool_rounds} tool round(s)"
            f"{suffix})"
        )
        for check in result.checks:
            if check.skipped:
                print(f"         – {check.name}: {check.detail}")
            elif check.known_gap and not check.passed:
                print(f"         ~ {check.name} (known gap): {check.detail}")
            elif check.known_gap and check.passed:
                print(
                    f"         ✓ {check.name}: known gap now PASSES — "
                    f"remove known_gap from {result.case.path.name}"
                )
            elif not check.passed:
                print(f"         ✗ {check.name}: {check.detail}")
        for score in result.rubric:
            if score.verdict != "pass":
                print(f"         · rubric {score.verdict}: {score.item}")
                print(f"                  {score.reason}")
        if result.judge_error:
            print(f"         · rubric not scored ({result.judge_error})")

    failed = [r for r in results if not r.passed]
    counts = _verdict_counts(results)
    total_skipped = sum(len(r.skipped_checks) for r in results)
    enforced = sum(len(r.checks) - len(r.skipped_checks) for r in results)
    print()
    print(
        f"{len(results) - len(failed)}/{len(results)} cases passed "
        f"({enforced} assertion(s) enforced"
        f"{f', {total_skipped} skipped' if total_skipped else ''})"
    )
    if any(counts.values()):
        print(
            f"rubric: {counts['pass']} pass, {counts['partial']} partial, "
            f"{counts['fail']} fail (advisory — does not gate)"
        )
    if failed:
        print("failed: " + ", ".join(f"{r.case.group}/{r.case.name}" for r in failed))

    open_gaps = [
        (r, c) for r in results for c in r.known_gap_checks if not c.passed and not c.skipped
    ]
    if open_gaps:
        print()
        print(f"known gaps still open ({len(open_gaps)}) — not gating, but not fixed either:")
        for result, check in open_gaps:
            gap = result.case.known_gap
            tracked = f" [{gap.tracked_in}]" if gap and gap.tracked_in else ""
            print(f"  · {result.case.group}/{result.case.name} · {check.name}{tracked}")
            if gap:
                print(f"    {gap.reason}")


def write_artifacts(results: list[CaseResult], *, fast: bool) -> Path:
    """Persist the run and return its directory."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "timestamp": stamp,
        "mode": "fast" if fast else "full",
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "assertions_enforced": sum(len(r.checks) - len(r.skipped_checks) for r in results),
        "assertions_skipped": sum(len(r.skipped_checks) for r in results),
        "rubric": _verdict_counts(results),
        "cases": [
            {
                "group": r.case.group,
                "name": r.case.name,
                "passed": r.passed,
                "duration_s": round(r.duration_s, 3),
                "tool_rounds": r.trace.tool_rounds,
                "retrieved_sources": r.trace.retrieved_sources,
                "failed_checks": [c.name for c in r.checks if not c.passed and not c.skipped],
                "skipped_checks": [c.name for c in r.skipped_checks],
            }
            for r in results
        ],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for result in results:
        detail = {
            "case": result.case.model_dump(mode="json"),
            "trace": asdict(result.trace),
            "checks": [asdict(c) for c in result.checks],
            "rubric": [asdict(s) for s in result.rubric],
            "judge_error": result.judge_error,
            "duration_s": round(result.duration_s, 3),
        }
        path = run_dir / f"{result.case.group}__{result.case.name}.json"
        path.write_text(json.dumps(detail, indent=2, ensure_ascii=False), encoding="utf-8")

    return run_dir
