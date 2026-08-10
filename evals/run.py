"""Eval suite entry point — invoked by `just eval`.

Usage:
    just eval                             # everything, real model, judged
    just eval -- --case scope             # one group (or one case name)
    just eval -- --tag prompt:main-agent  # everything touching that prompt
    just eval -- --fast                   # LLM_FAKE_MODE, no judge, CI-safe

Exit code is 1 when any hard assertion failed, so CI and `just` both stop on a
regression. Rubric verdicts never affect it — see prompts/system/eval-judge.md.

Cases run sequentially on purpose. The default model is a free-tier Gemini key
capped around 20 requests/day, and a parallel run would burn the day's budget
into rate-limit errors that look like agent failures.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the agent eval suite.")
    parser.add_argument("--case", help="Run only this case name, file stem, or group folder.")
    parser.add_argument("--tag", help="Run only cases carrying this tag.")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use the offline synthetic-answer path instead of a real model.",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip rubric scoring even on a full run (saves one LLM call per case).",
    )
    args = parser.parse_args()

    # Set before `agent.settings` is imported: Settings reads the environment
    # once at construction, so flipping the flag after import would be silently
    # ignored and --fast would quietly run against the real provider.
    if args.fast:
        os.environ["LLM_FAKE_MODE"] = "true"

    from .case import discover_cases
    from .report import print_summary, write_artifacts
    from .runner import run_case

    cases = discover_cases(case=args.case, tag=args.tag)
    if not cases:
        print("[evals] no cases matched — nothing to run.", file=sys.stderr)
        return 1

    judge = not (args.fast or args.no_judge)
    print(f"[evals] running {len(cases)} case(s){'' if judge else ' (rubric judging off)'}")

    async def run_all():
        return [await run_case(c, judge=judge, fast=args.fast) for c in cases]

    results = asyncio.run(run_all())

    print_summary(results, fast=args.fast)
    run_dir = write_artifacts(results, fast=args.fast)
    print(f"\nartifacts: {run_dir}")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
