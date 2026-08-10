"""Tests for the assertion layer.

These matter more than they look. A check that silently never fires is
indistinguishable from a check that passes, so a broken assertion turns the
whole suite into decoration — which is exactly what happened before: the
Acelents case blocklisted ``npm install`` with plain substring matching, so
every correct answer saying ``pnpm install`` tripped it and the case could
never have gone green.

No agent import, no model, no index — this file runs in milliseconds.
"""

from __future__ import annotations

import json

import pytest

from .case import Expectations, KnownGap
from .checks import (
    Check,
    RunTrace,
    ToolInvocation,
    evaluate,
    extract_retrieved_sources,
    mentions,
)


def _by_name(checks: list[Check], name: str) -> Check:
    return next(c for c in checks if c.name == name)


class TestMentions:
    def test_pnpm_install_does_not_trip_an_npm_install_blocklist(self):
        """The bug this function exists for."""
        assert not mentions("npm install", "Jalankan `pnpm install` lalu `pnpm dev`.")
        assert mentions("npm install", "Run npm install first")

    @pytest.mark.parametrize(
        ("needle", "text"),
        [
            ("docker-compose", "just run docker-compose up"),
            ("localhost:3000", "open http://localhost:3000 in your browser"),
            ("db:migrate", "then npm run db:migrate"),
            ("Amazon Chime", "powered by amazon chime under the hood"),
        ],
    )
    def test_blocklist_needles_still_match(self, needle, text):
        assert mentions(needle, text)

    def test_prefix_patterns_match_invented_suffixes(self):
        """ZEPHYR_SSO_ exists to catch ZEPHYR_SSO_ENABLED and friends.

        This is why only the leading edge gets a word boundary — a trailing one
        would refuse to match, since `_E` is two word characters in a row.
        """
        assert mentions("ZEPHYR_SSO_", "set ZEPHYR_SSO_ENABLED=true")

    def test_needles_starting_with_punctuation_fall_back_to_substring(self):
        assert mentions("![", "here it is: ![Halaman Tour](http://x/y.png)")
        assert mentions("/screenshots/", "http://localhost:8000/screenshots/tour.png")

    def test_matching_is_case_insensitive(self):
        assert mentions("pnpm dev", "Jalankan PNPM DEV")


class TestExtractRetrievedSources:
    def test_reads_sources_out_of_a_search_reply(self):
        content = json.dumps(
            {
                "chunks": [
                    {"source": "docs/products/acelents/product.md", "text": "...", "score": 0.9},
                    {
                        "source": "docs/knowledge-base/klob-doc-context.md",
                        "text": "...",
                        "score": 0.4,
                    },
                ],
                "warning": None,
            }
        )
        assert extract_retrieved_sources("search_documentation", content) == [
            "docs/products/acelents/product.md",
            "docs/knowledge-base/klob-doc-context.md",
        ]

    def test_other_tools_contribute_nothing(self):
        content = json.dumps({"chunks": [{"source": "x.md"}]})
        assert extract_retrieved_sources("capture_screenshot", content) == []

    def test_a_tool_error_string_yields_nothing_instead_of_raising(self):
        assert extract_retrieved_sources("search_documentation", "error: boom") == []


class TestToolAssertions:
    def test_missing_tool_fails_and_names_it(self):
        trace = RunTrace(tool_calls=[ToolInvocation("list_products", {})])
        checks = evaluate(trace, Expectations(must_call_tool=["search_documentation"]))
        check = _by_name(checks, "must_call_tool")
        assert not check.passed
        assert "search_documentation" in check.detail

    def test_order_is_only_enforced_when_asked(self):
        trace = RunTrace(
            tool_calls=[
                ToolInvocation("capture_screenshot", {}),
                ToolInvocation("search_documentation", {}),
            ]
        )
        unordered = Expectations(must_call_tool=["search_documentation", "capture_screenshot"])
        assert _by_name(evaluate(trace, unordered), "must_call_tool").passed

        ordered = Expectations(
            must_call_tool=["search_documentation", "capture_screenshot"],
            must_call_tool_in_order=True,
        )
        assert not _by_name(evaluate(trace, ordered), "must_call_tool_in_order").passed

    def test_scope_must_hold_on_every_call_not_just_one(self):
        """The ADR 0009 guarantee is 'no search escapes', so one leak is a fail."""
        trace = RunTrace(
            tool_calls=[
                ToolInvocation("search_documentation", {"product_id": "tep-cms"}),
                ToolInvocation("search_documentation", {"product_id": "klob"}),
            ]
        )
        expected = Expectations(
            tool_args_must_include={"search_documentation": {"product_id": "tep-cms"}}
        )
        check = _by_name(evaluate(trace, expected), "tool_args_must_include")
        assert not check.passed
        assert "call 1" in check.detail

    def test_uncalled_tool_fails_the_args_assertion(self):
        expected = Expectations(
            tool_args_must_include={"search_documentation": {"product_id": "tep-cms"}}
        )
        check = _by_name(evaluate(RunTrace(), expected), "tool_args_must_include")
        assert not check.passed
        assert "never called" in check.detail

    def test_round_budget_is_reached_not_exceeded(self):
        assert _by_name(
            evaluate(RunTrace(tool_rounds=6), Expectations(max_tool_rounds=6)), "max_tool_rounds"
        ).passed
        assert not _by_name(
            evaluate(RunTrace(tool_rounds=7), Expectations(max_tool_rounds=6)), "max_tool_rounds"
        ).passed


class TestRetrievalAssertion:
    def test_partial_paths_match_so_cases_do_not_pin_the_folder_layout(self):
        trace = RunTrace(retrieved_sources=["docs/products/acelents/product.md"])
        expected = Expectations(must_retrieve_any=["acelents/product.md"])
        assert _by_name(evaluate(trace, expected), "must_retrieve_any").passed

    def test_wrong_documents_fail_and_the_detail_shows_what_came_back(self):
        trace = RunTrace(retrieved_sources=["docs/knowledge-base/tep-cms-doc-context.md"])
        expected = Expectations(must_retrieve_any=["docs/products/acelents/product.md"])
        check = _by_name(evaluate(trace, expected), "must_retrieve_any")
        assert not check.passed
        assert "tep-cms" in check.detail


class TestDeclaredOnly:
    def test_undeclared_assertions_produce_no_checks(self):
        """An empty expectation is silence, not a free pass padding the count."""
        assert evaluate(RunTrace(final_answer="anything"), Expectations()) == []

    def test_a_graph_error_fails_the_case_on_its_own(self):
        checks = evaluate(RunTrace(error="RuntimeError: boom"), Expectations())
        assert not _by_name(checks, "no_error").passed


class TestFastMode:
    def test_model_dependent_checks_are_skipped_not_passed(self):
        trace = RunTrace(final_answer="this answer contains docker-compose")
        expected = Expectations(
            must_not_contain=["docker-compose"],
            must_retrieve_any=["acelents"],
        )

        full = evaluate(trace, expected)
        assert not _by_name(full, "must_not_contain").passed

        fast = evaluate(trace, expected, fast=True)
        blocked = _by_name(fast, "must_not_contain")
        assert blocked.skipped
        assert "not evaluated" in blocked.detail
        # Retrieval is real in both modes, so it must still be judged.
        assert not _by_name(fast, "must_retrieve_any").skipped


class TestKnownGap:
    def test_a_marked_failure_does_not_count_against_the_build(self):
        trace = RunTrace(retrieved_sources=["wrong.md"])
        expected = Expectations(must_retrieve_any=["right.md"])
        gap = KnownGap(checks=["must_retrieve_any"], reason="tracked elsewhere")

        check = _by_name(evaluate(trace, expected, known_gap=gap), "must_retrieve_any")
        assert not check.passed
        assert check.known_gap
        assert not check.counts_against_the_build

    def test_an_unmarked_failure_still_counts(self):
        trace = RunTrace(retrieved_sources=["wrong.md"])
        expected = Expectations(must_retrieve_any=["right.md"])
        check = _by_name(evaluate(trace, expected), "must_retrieve_any")
        assert check.counts_against_the_build

    def test_a_gap_that_now_passes_stays_marked_so_it_can_be_reported(self):
        trace = RunTrace(retrieved_sources=["right.md"])
        expected = Expectations(must_retrieve_any=["right.md"])
        gap = KnownGap(checks=["must_retrieve_any"], reason="tracked elsewhere")

        check = _by_name(evaluate(trace, expected, known_gap=gap), "must_retrieve_any")
        assert check.passed and check.known_gap
