"""Eval runner skeleton.

Real implementation is wired against the LangGraph agent in
`apps/backend/src/agent/graph.py`. This module is the entry point invoked
by `just eval`.

Usage:
    uv run python -m evals.run [--case NAME] [--tag TAG] [--fast]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CASES_DIR = Path(__file__).parent / "cases"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the agent eval suite.")
    parser.add_argument("--case", help="Run only this case (by name).")
    parser.add_argument("--tag", help="Run only cases with this tag.")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use cached/mocked LLM responses where available.",
    )
    args = parser.parse_args()

    # TODO: discover YAML cases under CASES_DIR
    # TODO: load each, invoke the LangGraph agent, capture tool trace + final message
    # TODO: check `must_call_tool`, `must_contain_any`, `must_not_contain`
    # TODO: optionally run rubric judge (separate LLM call)
    # TODO: write summary + per-case details to evals/.runs/<timestamp>/
    print("[evals] runner not yet implemented — scaffolding only", file=sys.stderr)
    print(f"[evals] cases dir: {CASES_DIR}", file=sys.stderr)
    print(f"[evals] args: {args}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
