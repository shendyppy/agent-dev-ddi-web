"""Tests for the retry policy in agent.llm.

The distinction under test is the one that matters in practice: a per-minute
rate limit is worth waiting out, a per-day quota is not. Getting it wrong is
silent — the user just waits through the full backoff ladder and receives the
same 429 at the end.
"""

from __future__ import annotations

import json

import pytest
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError,
)

from .llm import (
    _extract_chunks,
    _first_tool_result,
    _last_user_question,
    _render_retrieved_answer,
    _should_retry,
    is_daily_quota_error,
)

# The shape LiteLLM produces for an exhausted Gemini free tier: the provider
# payload is flattened into the exception string, and the only thing marking it
# as a daily limit is the quotaId.
GEMINI_DAILY_QUOTA = (
    "litellm.RateLimitError: geminiException - {"
    '"error": {"code": 429, "message": "You exceeded your current quota. '
    "Quota exceeded for metric: generativelanguage.googleapis.com/"
    'generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash. '
    'Please retry in 25.003971798s.", "status": "RESOURCE_EXHAUSTED", '
    '"details": [{"violations": [{"quotaId": '
    '"GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]}]}}'
)


def _rate_limit(message: str) -> RateLimitError:
    return RateLimitError(message, llm_provider="gemini", model="gemini-3.6-flash")


class TestIsDailyQuotaError:
    def test_detects_gemini_free_tier_daily_quota(self) -> None:
        assert is_daily_quota_error(_rate_limit(GEMINI_DAILY_QUOTA))

    @pytest.mark.parametrize(
        "message",
        [
            "429 quota exceeded: requests per day",
            "Quota exceeded — GenerateRequestsPerDay-FreeTier",
            "limit reached: 20 REQUESTS PER DAY",  # matching is case-insensitive
        ],
    )
    def test_detects_other_daily_phrasings(self, message: str) -> None:
        assert is_daily_quota_error(_rate_limit(message))

    @pytest.mark.parametrize(
        "message",
        [
            "429 rate limit exceeded, requests per minute",
            "Quota exceeded for metric: generate_requests_per_minute",
            "RESOURCE_EXHAUSTED: too many concurrent requests",
        ],
    )
    def test_ignores_non_daily_limits(self, message: str) -> None:
        assert not is_daily_quota_error(_rate_limit(message))


class TestShouldRetry:
    def test_daily_quota_is_not_retried(self) -> None:
        """The regression this module exists for: retrying burns ~35s to fail
        with the identical error, because the quota resets at midnight, not
        after a backoff."""
        assert not _should_retry(_rate_limit(GEMINI_DAILY_QUOTA))

    def test_per_minute_rate_limit_is_retried(self) -> None:
        assert _should_retry(_rate_limit("429 too many requests per minute"))

    @pytest.mark.parametrize(
        "exc",
        [
            ServiceUnavailableError("503 overloaded", llm_provider="gemini", model="x"),
            APIConnectionError(  # type: ignore[call-arg]
                message="connection reset", llm_provider="gemini", model="x"
            ),
        ],
    )
    def test_transient_provider_errors_are_retried(self, exc: BaseException) -> None:
        assert _should_retry(exc)

    def test_non_retryable_types_are_rejected(self) -> None:
        """Auth and programming errors must fail fast rather than be retried."""
        assert not _should_retry(
            AuthenticationError("401 bad key", llm_provider="gemini", model="x")
        )
        assert not _should_retry(ValueError("bad argument"))


SEARCH_OUTPUT = {
    "chunks": [
        {
            "text": "Jalankan `just index` untuk membangun ulang ChromaDB.",
            "source": "docs/guides/indexing.md",
            "score": 0.81,
            "metadata": {"heading_path": "Indexing > Rebuild"},
        }
    ],
    "warning": None,
}


class TestExtractChunks:
    """The MCP layer can hand back the search result in several nestings
    depending on how the client unwrapped it. The parser walks down until it
    finds the payload rather than assuming one shape — these are the shapes it
    has to survive."""

    def test_plain_json_object(self) -> None:
        chunks, warning = _extract_chunks(json.dumps(SEARCH_OUTPUT))
        assert len(chunks) == 1
        assert warning is None

    def test_mcp_text_content_blocks(self) -> None:
        payload = json.dumps([{"type": "text", "text": json.dumps(SEARCH_OUTPUT)}])
        chunks, _ = _extract_chunks(payload)
        assert chunks[0]["source"] == "docs/guides/indexing.md"

    def test_wrapped_under_result_key(self) -> None:
        chunks, _ = _extract_chunks(json.dumps({"result": SEARCH_OUTPUT}))
        assert len(chunks) == 1

    def test_warning_is_returned(self) -> None:
        payload = json.dumps({"chunks": [], "warning": "index is empty"})
        chunks, warning = _extract_chunks(payload)
        assert chunks == []
        assert warning == "index is empty"

    @pytest.mark.parametrize(
        "payload",
        [
            "error: tool 'search_documentation' raised RuntimeError",  # not JSON
            json.dumps({"unexpected": "shape"}),
            json.dumps([]),
            "",
        ],
    )
    def test_unusable_payloads_degrade_quietly(self, payload: str) -> None:
        """Anything unparseable must return no chunks rather than raise — the
        caller falls back to the static fixture on an empty result."""
        chunks, _ = _extract_chunks(payload)
        assert chunks == []


class TestFakeAnswerHelpers:
    def test_last_user_question_ignores_later_roles(self) -> None:
        messages = [
            {"role": "user", "content": "pertanyaan pertama"},
            {"role": "assistant", "content": "jawaban"},
            {"role": "user", "content": "pertanyaan kedua"},
            {"role": "tool", "content": "{}"},
        ]
        assert _last_user_question(messages) == "pertanyaan kedua"

    def test_first_tool_result_gates_the_second_phase(self) -> None:
        """Any tool message at all moves the fake to its answering phase, so it
        can never request a second search and spin the graph."""
        assert _first_tool_result([{"role": "user", "content": "hi"}]) is None
        assert _first_tool_result([{"role": "tool", "content": "payload"}]) == "payload"

    def test_rendered_answer_carries_real_sources(self) -> None:
        answer = _render_retrieved_answer("gimana cara indexing?", SEARCH_OUTPUT["chunks"], None)
        assert "gimana cara indexing?" in answer
        assert "Indexing > Rebuild" in answer
        # The Sources block is what the FE's CitationList parses out.
        assert "Sources:" in answer
        assert "- docs/guides/indexing.md" in answer

    def test_retrieval_warning_is_surfaced(self) -> None:
        answer = _render_retrieved_answer("q", SEARCH_OUTPUT["chunks"], "index is stale")
        assert "index is stale" in answer

    def test_long_chunks_are_excerpted(self) -> None:
        """A chunk can be thousands of characters; the transcript is the thing
        under test, not the corpus."""
        chunks = [{"text": "x" * 2000, "source": "a.md", "score": 0.5, "metadata": {}}]
        answer = _render_retrieved_answer("q", chunks, None)
        assert "…" in answer
        assert len(answer) < 1200
