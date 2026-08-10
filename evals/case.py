"""The eval case schema — the contract between a YAML file and the runner.

Pydantic rather than raw dicts because a case that silently does nothing is
worse than a case that fails loudly: a typo'd ``must_not_contian`` in a plain
dict would just never be checked, and the suite would report green while the
regression it was written for walked straight back in. ``extra="forbid"``
turns that typo into a load error.

The vocabulary here matches ``evals/README.md``; see that file for the
narrative version.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

CASES_DIR = Path(__file__).parent / "cases"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseMessage(Strict):
    role: Literal["user", "assistant", "system"]
    content: str


class CaseInput(Strict):
    """The turn to replay.

    ``product_id`` mirrors the UI's product picker. ``None`` is the explicit
    "all products" choice, and the difference matters: with a scope set, the
    orchestrator rewrites every ``search_documentation`` call's ``product_id``
    (ADR 0009), which is exactly what the scope cases assert.
    """

    messages: list[CaseMessage]
    product_id: str | None = None


class Expectations(Strict):
    """What has to be true about the run.

    Hard checks fail the case. ``rubric`` is scored by a judge model and
    reported, never fatal — a rubric is a nudge about quality, and wiring
    quality opinions to a red build makes people delete the rubric.
    """

    must_call_tool: list[str] = Field(default_factory=list)
    # When true, must_call_tool is read as a sequence: the listed tools have to
    # appear in the trace in that relative order (other calls may interleave).
    must_call_tool_in_order: bool = False
    # Every arg listed has to be present, with that value, on EVERY call to the
    # named tool. "Every" rather than "at least one" is deliberate: the scope
    # guarantee is that no search escapes the focused product, and a check that
    # only looked at one call would pass a run that leaked on the second.
    tool_args_must_include: dict[str, dict[str, Any]] = Field(default_factory=dict)
    max_tool_rounds: int | None = None

    # Retrieval quality, checked against the `source` metadata that
    # search_documentation actually returned — not against the answer text.
    # Without this the suite can only ask "did the answer contain the right
    # words", which passes just as happily when the model guessed correctly
    # from a bad retrieval. Retrieval and generation fail for different reasons
    # and need different fixes, so they need separate assertions.
    must_retrieve_any: list[str] = Field(default_factory=list)

    must_contain_any: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)

    rubric: list[str] = Field(default_factory=list)


class KnownGap(Strict):
    """A check we know fails today, recorded rather than deleted.

    The alternative to this field is one of two bad options: weaken the
    assertion until it matches current behaviour — which bakes the defect in as
    the spec — or leave the suite red, which teaches everyone to ignore it. Both
    end with the gap forgotten.

    A marked check still runs and still reports its real state; it just does not
    fail the build. If it starts passing, the report says so and asks for the
    marker to be removed, so a fixed gap cannot quietly stay marked.
    """

    checks: list[str]
    reason: str
    # Where the fix is tracked — an ADR number, an issue, a plan phase.
    tracked_in: str = ""


class Case(Strict):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    input: CaseInput
    expected: Expectations = Field(default_factory=Expectations)
    known_gap: KnownGap | None = None

    # Filled in by the loader so failures can name the file, not just the case.
    path: Path = Field(exclude=True)

    @property
    def group(self) -> str:
        """The folder the case lives in — ``search-docs``, ``scope``, ..."""
        return self.path.parent.name


def load_case(path: Path) -> Case:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Case(**data, path=path)


def discover_cases(
    *,
    case: str | None = None,
    tag: str | None = None,
    cases_dir: Path = CASES_DIR,
) -> list[Case]:
    """Load every case, optionally narrowed by ``--case`` or ``--tag``.

    ``--case`` matches a case name, a file stem, or a group folder, because all
    three are things people naturally type (``just eval -- --case search-docs``
    in the README is a *folder*, while ``--case unknown-product-refusal`` is a
    name). Guessing wrong is cheap; making someone remember which is which is
    not.
    """
    cases = sorted(
        (load_case(p) for p in cases_dir.rglob("*.yaml")),
        key=lambda c: (c.group, c.name),
    )
    if case:
        cases = [c for c in cases if case in (c.name, c.path.stem, c.group)]
    if tag:
        cases = [c for c in cases if tag in c.tags]
    return cases
