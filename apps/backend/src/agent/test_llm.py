"""Tests for the failure policy in agent.llm.

Two decisions are under test, both silent when wrong:

1. Retry or not. A per-minute rate limit is worth waiting out, a per-day quota
   is not — get it wrong and the user waits through the full backoff ladder to
   receive the same 429 at the end.
2. Degrade or raise. A capacity error becomes a local, quoted answer; anything
   else (auth, validation, a retired model id) must still reach the user as an
   error, because dressing a misconfiguration up as an answer hides it.
"""

from __future__ import annotations

import json

import pytest
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)

from . import llm as llm_module
from .llm import (
    _FALLBACK_WINDOW_DAILY_QUOTA,
    _FALLBACK_WINDOW_TRANSIENT,
    _enter_fallback,
    _extract_chunks,
    _first_tool_result,
    _last_user_question,
    _render_nothing_relevant,
    _render_retrieved_answer,
    _select_best_chunks,
    _should_retry,
    fallback_active,
    is_capacity_error,
    is_daily_quota_error,
    reset_fallback,
)

# The shape LiteLLM produces for an exhausted Gemini free tier: the provider
# payload is flattened into the exception string, and the only thing marking it
# as a daily limit is the quotaId.
GEMINI_DAILY_QUOTA = (
    "litellm.RateLimitError: geminiException - {"
    '"error": {"code": 429, "message": "You exceeded your current quota. '
    "Quota exceeded for metric: generativelanguage.googleapis.com/"
    "generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash. "
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


class TestIsCapacityError:
    """Which failures are allowed to degrade into a local answer."""

    @pytest.mark.parametrize(
        "exc",
        [
            _rate_limit("429 too many requests per minute"),
            _rate_limit(GEMINI_DAILY_QUOTA),
            ServiceUnavailableError("503 model is overloaded", llm_provider="gemini", model="x"),
            InternalServerError("500 internal", llm_provider="gemini", model="x"),
            APIConnectionError(  # type: ignore[call-arg]
                message="connection reset", llm_provider="gemini", model="x"
            ),
        ],
    )
    def test_capacity_failures_qualify(self, exc: BaseException) -> None:
        assert is_capacity_error(exc)

    @pytest.mark.parametrize(
        "exc",
        [
            AuthenticationError("401 bad key", llm_provider="gemini", model="x"),
            NotFoundError(  # a retired model id — 429 is not 404
                message="model is no longer available to new users",
                model="gemini-2.5-flash",
                llm_provider="gemini",
            ),
            ValueError("bad argument"),
        ],
    )
    def test_configuration_failures_must_surface(self, exc: BaseException) -> None:
        """Degrading these would hide a broken config behind plausible answers."""
        assert not is_capacity_error(exc)


class TestFallbackWindow:
    """The runtime switch that replaces the old LLM_FAKE_MODE env toggle: off at
    boot, opened by a capacity failure, closed again by time."""

    @pytest.fixture(autouse=True)
    def _clean_state(self) -> None:
        reset_fallback()

    def test_closed_at_boot(self) -> None:
        assert not fallback_active()

    def test_opened_by_a_transient_failure(self) -> None:
        _enter_fallback(ServiceUnavailableError("503 overloaded", llm_provider="gemini", model="x"))
        assert fallback_active()

    def test_daily_quota_gets_the_longer_window(self) -> None:
        """A per-day quota cannot clear until midnight Pacific, so probing the
        provider every two minutes is pure waste."""
        _enter_fallback(_rate_limit(GEMINI_DAILY_QUOTA))
        quota_deadline = llm_module._fallback_deadline
        reset_fallback()
        _enter_fallback(_rate_limit("429 per minute"))
        transient_deadline = llm_module._fallback_deadline

        assert quota_deadline is not None and transient_deadline is not None
        assert quota_deadline - transient_deadline == pytest.approx(
            _FALLBACK_WINDOW_DAILY_QUOTA - _FALLBACK_WINDOW_TRANSIENT, abs=1.0
        )

    def test_expiry_closes_the_window_and_clears_the_deadline(self) -> None:
        """Self-healing: the turn after the window lapses hits the real provider
        again, so a momentary 503 does not leave the chat degraded for good."""
        _enter_fallback(_rate_limit("429 per minute"))
        llm_module._fallback_deadline = 0.0  # a deadline already in the past
        assert not fallback_active()
        assert llm_module._fallback_deadline is None


class TestAcompletionDegradesInsteadOfFailing:
    """End to end through the gateway: what the caller gets back when the
    provider says no. This is the behaviour the FE used to render as a red
    error bubble."""

    @pytest.fixture(autouse=True)
    def _clean_state(self) -> None:
        reset_fallback()

    async def _acompletion_raising(
        self, monkeypatch: pytest.MonkeyPatch, exc: BaseException
    ) -> object:
        calls = {"n": 0}

        async def _boom(**_kwargs: object) -> object:
            calls["n"] += 1
            raise exc

        monkeypatch.setattr(llm_module.litellm, "acompletion", _boom)
        # One attempt only: the retry ladder is not what these tests are about.
        monkeypatch.setattr(llm_module.settings, "litellm_max_attempts", 1)
        response = await llm_module.acompletion([{"role": "user", "content": "cara indexing?"}])
        assert calls["n"] == 1
        return response

    async def test_capacity_error_returns_a_local_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The turn that *triggers* the outage still gets answered — it asks for
        retrieval, and the graph loops back for the quoted answer."""
        response = await self._acompletion_raising(monkeypatch, _rate_limit(GEMINI_DAILY_QUOTA))
        message = response.choices[0].message
        assert message.tool_calls is not None
        assert message.tool_calls[0]["function"]["name"] == "search_documentation"
        assert fallback_active()

    async def test_second_call_skips_the_provider_entirely(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Once the window is open no further quota is burned — the point of
        opening it. `_boom` would raise if litellm were touched again."""
        await self._acompletion_raising(monkeypatch, _rate_limit(GEMINI_DAILY_QUOTA))
        response = await llm_module.acompletion(
            [
                {"role": "user", "content": "cara indexing?"},
                {"role": "tool", "content": json.dumps(SEARCH_OUTPUT)},
            ]
        )
        assert "Model sedang tidak bisa dihubungi" in response.choices[0].message.content

    async def test_auth_error_still_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A bad key is not an outage. Answering around it would leave the key
        broken and the logs quiet."""
        with pytest.raises(AuthenticationError):
            await self._acompletion_raising(
                monkeypatch,
                AuthenticationError("401 bad key", llm_provider="gemini", model="x"),
            )
        assert not fallback_active()


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

    def test_answer_says_the_model_is_not_in_the_loop(self) -> None:
        """The user has to be told this is a quote, not an answer the model
        composed — otherwise a verbatim doc dump reads as the agent's own words."""
        answer = _render_retrieved_answer("q", SEARCH_OUTPUT["chunks"], None)
        assert "Model sedang tidak bisa dihubungi" in answer
        assert "dikutip apa adanya" in answer

    def test_single_passage_is_not_numbered(self) -> None:
        """A leading `1.` on a lone heading reads like the list got truncated."""
        answer = _render_retrieved_answer("q", SEARCH_OUTPUT["chunks"], None)
        assert "### Indexing > Rebuild" in answer

    def test_retrieval_warning_is_surfaced(self) -> None:
        answer = _render_retrieved_answer("q", SEARCH_OUTPUT["chunks"], "index is stale")
        assert "index is stale" in answer

    def test_long_chunks_are_excerpted(self) -> None:
        """A chunk can be thousands of characters; the transcript is the thing
        under test, not the corpus."""
        chunks = [{"text": "x" * 2000, "source": "a.md", "score": 0.5, "metadata": {}}]
        answer = _render_retrieved_answer("q", chunks, None)
        assert "…" in answer
        # 700-char excerpt + the offline note + one citation, nothing more.
        assert len(answer) < 1400

    def test_nothing_relevant_is_an_honest_dead_end(self) -> None:
        """No chunks cleared the floor: say so and suggest a next step, rather
        than quoting whatever came back."""
        answer = _render_nothing_relevant("cara deploy", "index is empty")
        assert "Belum bisa dijawab sekarang" in answer
        assert "cara deploy" in answer
        assert "index is empty" in answer
        assert "Sources:" not in answer


def _chunk(
    score: float | None,
    source: str = "a.md",
    text: str = "isi dokumen",
    heading: str = "",
) -> dict[str, object]:
    chunk: dict[str, object] = {
        "text": text,
        "source": source,
        "metadata": {"heading_path": heading} if heading else {},
    }
    if score is not None:
        chunk["score"] = score
    return chunk


class TestSelectBestChunks:
    """`search_documentation` returns a fixed top_k regardless of quality, so
    the tail of its list is usually a chunk that merely shares a word with the
    question. Printing it all buries the passage that actually answers."""

    def test_keeps_the_best_match_and_its_near_ties(self) -> None:
        selected = _select_best_chunks([_chunk(0.82, "a.md"), _chunk(0.78, "b.md")])
        assert [c["source"] for c in selected] == ["a.md", "b.md"]

    def test_drops_matches_clearly_worse_than_the_best(self) -> None:
        selected = _select_best_chunks(
            [_chunk(0.82, "a.md"), _chunk(0.45, "b.md"), _chunk(0.31, "c.md")]
        )
        assert [c["source"] for c in selected] == ["a.md"]

    def test_orders_by_score_regardless_of_input_order(self) -> None:
        selected = _select_best_chunks([_chunk(0.75, "b.md"), _chunk(0.80, "a.md")])
        assert [c["source"] for c in selected] == ["a.md", "b.md"]

    def test_caps_the_number_of_passages(self) -> None:
        selected = _select_best_chunks([_chunk(0.80, f"{i}.md") for i in range(6)])
        assert len(selected) == 3

    def test_nothing_relevant_when_even_the_best_is_weak(self) -> None:
        """A wall of near-misses is worse than admitting the index has nothing:
        it looks authoritative and answers a different question."""
        assert _select_best_chunks([_chunk(0.12), _chunk(0.05), _chunk(-0.3)]) == []

    def test_unscored_chunks_fall_back_to_retriever_order(self) -> None:
        """A retriever that does not score at all must not be read as empty."""
        chunks = [_chunk(None, f"{i}.md") for i in range(5)]
        selected = _select_best_chunks(chunks)
        assert [c["source"] for c in selected] == ["0.md", "1.md", "2.md"]

    def test_empty_input_stays_empty(self) -> None:
        assert _select_best_chunks([]) == []


class TestKeywordGate:
    """Measured against the real index, the similarity score cannot tell an
    off-topic Indonesian question ("resep rendang padang", top score 0.514) from
    an on-topic one ("gimana cara menjalankan proyek ini di lokal?", 0.501) —
    bge-small-en reads all Indonesian text as roughly equidistant. Keyword
    overlap separated the same queries cleanly (on topic 3-10, off topic 0-1),
    so overlap gates and the score only breaks ties."""

    QUESTION = "gimana cara menjalankan proyek ini di lokal?"

    def test_how_to_framing_does_not_make_a_passage_relevant(self) -> None:
        """`cara` is in most headings of this corpus ("Cara Menjalankan", "Cara
        Membaca", "Cara Kerja"), so it cannot be allowed to count: a contents
        page whose only tie to the question is the word "cara" is eliminated
        outright, not merely ranked second."""
        toc = _chunk(0.50, "toc.md", heading="Cara Membaca Dokumen Ini", text="daftar isi")
        answer = _chunk(
            0.49,
            "run.md",
            heading="Tech Stack > Menjalankan di lokal",
            text="npm i lalu npm run dev untuk proyek ini",
        )
        selected = _select_best_chunks([toc, answer], self.QUESTION)
        assert [c["source"] for c in selected] == ["run.md"]

    def test_off_topic_how_to_questions_are_rejected(self) -> None:
        """The regression this stopword group exists for: "gimana cara bikin kopi
        susu" used to come back with a documentation contents page."""
        toc = _chunk(
            0.49, "toc.md", heading="TEP CMS > Cara Membaca Dokumen Ini", text="cara bikin"
        )
        assert _select_best_chunks([toc], "gimana cara bikin kopi susu yang enak") == []

    def test_short_product_acronyms_still_count(self) -> None:
        """A four-character floor threw away `tep` and `cms` — the two words that
        identify the product — and answered "nothing found" to a question the
        index had a 0.662 match for."""
        chunk = _chunk(
            0.66,
            "tep.md",
            heading="TEP CMS — Feature Context > Tech Stack",
            text="React, Vite, Tailwind",
        )
        selected = _select_best_chunks([chunk], "teknologi apa yang dipakai di TEP CMS?")
        assert [c["source"] for c in selected] == ["tep.md"]

    def test_a_short_word_does_not_match_mid_token(self) -> None:
        """Prefix-of-token, not substring-of-text: as a bare substring `tep`
        would hit "step" and `api` would hit "aplikasi"."""
        decoy = _chunk(0.60, "decoy.md", heading="Langkah Setup", text="step by step aplikasi ini")
        assert _select_best_chunks([decoy], "TEP API") == []

    def test_a_titled_section_beats_a_table_of_contents(self) -> None:
        """The exact shape observed against the real index: a contents table
        mentions every topic in its cells, so on body text alone it ties with
        the section that answers. The heading is what breaks it."""
        toc = _chunk(
            0.50,
            "toc.md",
            heading="TEP CMS > Cara Membaca Dokumen Ini",
            text="| Cara jalanin di lokal | Tech Stack & Cara Menjalankan |",
        )
        answer = _chunk(
            0.49,
            "run.md",
            heading="TEP CMS > Cara Menjalankan > Menjalankan di lokal",
            text="npm i lalu npm run dev",
        )
        selected = _select_best_chunks([toc, answer], self.QUESTION)
        assert [c["source"] for c in selected] == ["run.md", "toc.md"]

    def test_a_high_score_does_not_survive_zero_overlap(self) -> None:
        """The consequence of trusting overlap over the score: a chunk that
        mentions nothing the user asked about is dropped even at 0.82, because on
        this corpus a high score is not evidence of being on topic."""
        mute = _chunk(0.82, "mute.md", text="tidak menyebut kata apa pun")
        on_topic = _chunk(0.40, "on-topic.md", heading="Menjalankan di lokal", text="npm run dev")
        selected = _select_best_chunks([mute, on_topic], self.QUESTION)
        assert [c["source"] for c in selected] == ["on-topic.md"]

    def test_score_breaks_ties_between_equally_on_topic_passages(self) -> None:
        weaker = _chunk(0.45, "weaker.md", heading="Menjalankan di lokal", text="npm run dev")
        stronger = _chunk(0.61, "stronger.md", heading="Menjalankan di lokal", text="npm run dev")
        selected = _select_best_chunks([weaker, stronger], self.QUESTION)
        assert [c["source"] for c in selected] == ["stronger.md", "weaker.md"]

    def test_nothing_on_topic_returns_nothing(self) -> None:
        """The off-topic case that a score floor could not catch: decent scores,
        no shared vocabulary at all."""
        chunks = [
            _chunk(0.52, "a.md", heading="Manajemen Assessment", text="modul penilaian peserta"),
            _chunk(0.51, "b.md", heading="Peta Route", text="daftar halaman aplikasi"),
        ]
        assert _select_best_chunks(chunks, "resep rendang padang untuk lebaran") == []

    def test_a_question_with_no_content_words_falls_back_to_score(self) -> None:
        """Nothing to overlap against, so refusing to answer would be worse than
        a weak guess ranked by score."""
        selected = _select_best_chunks([_chunk(0.75, "b.md"), _chunk(0.80, "a.md")], "apa itu ini?")
        assert [c["source"] for c in selected] == ["a.md", "b.md"]

    def test_a_single_word_question_cannot_be_held_to_the_two_point_bar(self) -> None:
        """One content word found in the body scores 1, so a bar of 2 would
        reject every passage for a one-word question."""
        selected = _select_best_chunks(
            [_chunk(0.55, "a.md", text="modul assessment untuk peserta")], "assessment"
        )
        assert [c["source"] for c in selected] == ["a.md"]

    def test_grammar_words_do_not_count_as_topic(self) -> None:
        """Without a stopword guard, "ini"/"yang" would hand the tie to whichever
        chunk happens to be the most verbose."""
        chatty = _chunk(0.50, "chatty.md", text="ini yang itu dengan untuk dari pada proyek ini")
        precise = _chunk(0.50, "precise.md", heading="Menjalankan di lokal", text="npm run dev")
        selected = _select_best_chunks([chatty, precise], self.QUESTION)
        assert selected[0]["source"] == "precise.md"
