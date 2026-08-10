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

import inspect
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
    _FakeChoice,
    _FakeMessage,
    _FakeResponse,
    _first_tool_result,
    _last_user_question,
    _render_nothing_relevant,
    _render_retrieved_answer,
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


class TestResolveApiKey:
    """The four-layer order from ADR 0010. Every layer matters for a different
    caller: the user key is BYOK, the provider key is what lets a model picker
    offer more than one vendor at once, the generic key is the two-line .env
    swap, and None is what keeps every pre-ADR call behaving as it did."""

    MODEL = "gemini/gemini-3.6-flash"

    @pytest.fixture(autouse=True)
    def _no_ambient_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # litellm's import-time load_dotenv() puts the real .env into
        # os.environ, so without this the suite would read Shendy's actual key
        # and the assertions below would depend on his machine.
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(llm_module.settings, "model_api_key", None)

    def test_user_key_wins_over_everything(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "from-env")
        monkeypatch.setattr(llm_module.settings, "model_api_key", "generic")
        assert llm_module.resolve_api_key(self.MODEL, "from-user") == "from-user"

    def test_blank_user_key_is_not_a_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty header must fall through, not authenticate as ''."""
        monkeypatch.setenv("GEMINI_API_KEY", "from-env")
        assert llm_module.resolve_api_key(self.MODEL, "   ") == "from-env"

    def test_provider_key_beats_the_generic_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "from-env")
        monkeypatch.setattr(llm_module.settings, "model_api_key", "generic")
        assert llm_module.resolve_api_key(self.MODEL) == "from-env"

    def test_provider_name_comes_from_the_model_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point of deriving the provider: a different model reads a
        different variable with no code change."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
        assert llm_module.resolve_api_key("deepseek/deepseek-chat") == "ds-key"

    def test_generic_key_is_the_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_module.settings, "model_api_key", "generic")
        assert llm_module.resolve_api_key(self.MODEL) == "generic"

    def test_nothing_configured_resolves_to_none(self) -> None:
        """Layer 4 — the backwards-compatible path. Returning None is what lets
        acompletion omit api_key entirely and leave LiteLLM's own lookup alone."""
        assert llm_module.resolve_api_key(self.MODEL) is None

    def test_unknown_model_still_reaches_the_generic_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unrecognised model id is the provider's error to report, not a
        reason to fail before the request is even attempted."""
        monkeypatch.setattr(llm_module.settings, "model_api_key", "generic")
        assert llm_module.resolve_api_key("not-a-real-provider/whatever") == "generic"


class TestCredentialNeverLeaks:
    """ADR 0010 names three leak paths. These cover the one that lives in this
    module; each asserts on the key's literal value, so they fail loudly rather
    than drifting if the payload shape changes."""

    SECRET = "sk-must-never-appear-anywhere"

    @pytest.fixture(autouse=True)
    def _clean_state(self) -> None:
        reset_fallback()

    async def test_key_reaches_the_provider_but_not_the_trace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        traced: list[dict[str, object]] = []
        sent: dict[str, object] = {}

        async def _capture(**kwargs: object) -> object:
            sent.update(kwargs)
            return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="ok"))])

        class _Recorder:
            def update_current_generation(self, **kwargs: object) -> None:
                traced.append(kwargs)

        monkeypatch.setattr(llm_module.litellm, "acompletion", _capture)
        monkeypatch.setattr(llm_module, "get_client", lambda: _Recorder())
        monkeypatch.setattr(llm_module.settings, "llm_fake_mode", False)

        await llm_module.acompletion([{"role": "user", "content": "halo"}], api_key=self.SECRET)

        # It must actually be used, or BYOK does nothing.
        assert sent.get("api_key") == self.SECRET
        # …and it must not be anywhere Langfuse would persist.
        assert self.SECRET not in repr(traced)

    def test_observe_decorator_does_not_capture_arguments(self) -> None:
        """The leak the first version of this class MISSED.

        `@observe` captures the decorated function's arguments by default —
        `LANGFUSE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED` defaults to "True" and
        `_get_input_from_func_args` serialises **kwargs wholesale. `api_key` is
        a kwarg on `acompletion`, so every BYOK call on a Langfuse-enabled
        deployment wrote the user's credential into a trace.

        The other test in this class passed throughout, because it mocks
        `get_client` — the path `update_current_generation` uses. The decorator
        holds its own client and never went through the mock.

        Asserting on the source is deliberate. The decorator returns an opaque
        wrapper, so the configuration cannot be read back at runtime; this is
        the only way to make the security control fail loudly if it is removed.
        """
        source = inspect.getsource(llm_module)
        decorator = next(
            line for line in source.splitlines() if line.strip().startswith("@observe(")
        )
        assert "capture_input=False" in decorator, decorator
        assert "capture_output=False" in decorator, decorator

    async def test_no_api_key_is_passed_when_none_resolves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Omitted, not None. Passing api_key=None explicitly short circuits
        LiteLLM's own env lookup on some providers, which would silently break
        every deployment that relies on it today."""
        sent: dict[str, object] = {}

        async def _capture(**kwargs: object) -> object:
            sent.update(kwargs)
            return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="ok"))])

        monkeypatch.setattr(llm_module.litellm, "acompletion", _capture)
        monkeypatch.setattr(llm_module.settings, "llm_fake_mode", False)
        monkeypatch.setattr(llm_module, "resolve_api_key", lambda *_a, **_k: None)

        await llm_module.acompletion([{"role": "user", "content": "halo"}])
        assert "api_key" not in sent


class TestPerRequestOffline:
    """`offline=True` skips the provider for ONE call. It must not touch the
    process-wide flag, or the UI toggle it backs would degrade every other
    user's answers too."""

    @pytest.fixture(autouse=True)
    def _clean_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reset_fallback()
        monkeypatch.setattr(llm_module.settings, "llm_fake_mode", False)

    async def test_offline_call_never_reaches_the_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom(**_kwargs: object) -> object:
            raise AssertionError("provider was called despite offline=True")

        monkeypatch.setattr(llm_module.litellm, "acompletion", _boom)
        response = await llm_module.acompletion(
            [{"role": "user", "content": "cara indexing?"}], offline=True
        )
        assert response.choices[0].message.tool_calls is not None

    async def test_one_offline_call_does_not_affect_the_next(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The isolation that makes a per-user toggle safe."""
        calls = {"n": 0}

        async def _ok(**_kwargs: object) -> object:
            calls["n"] += 1
            return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="real"))])

        monkeypatch.setattr(llm_module.litellm, "acompletion", _ok)
        await llm_module.acompletion([{"role": "user", "content": "x"}], offline=True)
        assert calls["n"] == 0

        await llm_module.acompletion([{"role": "user", "content": "x"}])
        assert calls["n"] == 1
        assert llm_module.settings.llm_fake_mode is False


class TestAcompletionDegradesInsteadOfFailing:
    """End to end through the gateway: what the caller gets back when the
    provider says no. This is the behaviour the FE used to render as a red
    error bubble."""

    @pytest.fixture(autouse=True)
    def _clean_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reset_fallback()
        # CI exports LLM_FAKE_MODE=true for the eval suite, which would make
        # acompletion skip the provider before the failure under test happens.
        monkeypatch.setattr(llm_module.settings, "llm_fake_mode", False)

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

    def test_pipeline_internals_stay_out_of_the_prose(self) -> None:
        """Scores and inline paths are operator vocabulary, not an answer. The
        similarity score is doubly wrong to print: the embedding model is
        English and the corpus Indonesian, so the number cannot separate
        on-topic from off-topic. Paths belong only in the Sources block, where
        the FE turns them into citation chips."""
        answer = _render_retrieved_answer("q", SEARCH_OUTPUT["chunks"], None)
        assert "relevansi" not in answer
        assert "0.81" not in answer  # the chunk's score
        # The path appears exactly once: in the Sources block, not under the heading.
        assert answer.count("docs/guides/indexing.md") == 1

    def test_long_chunks_are_excerpted(self) -> None:
        """A chunk can be thousands of characters; the transcript is the thing
        under test, not the corpus."""
        chunks = [{"text": "x" * 2000, "source": "a.md", "score": 0.5, "metadata": {}}]
        answer = _render_retrieved_answer("q", chunks, None)
        assert "…" in answer
        # 700-char excerpt + the offline note + one citation, nothing more.
        assert len(answer) < 1400

    def test_excerpt_never_cuts_a_table_mid_row(self) -> None:
        """Chunks are markdown, and a GFM table chopped mid-row stops parsing
        as a table — the FE then shows raw pipe characters. The cut must land
        on a line boundary so a long table just loses rows."""
        rows = "\n".join(f"| Modul {i} | `/route-{i}` | `/add` | `/edit/:id` |" for i in range(40))
        table = "| Modul | Route | Add | Edit |\n|---|---|---|---|\n" + rows
        chunks = [{"text": table, "source": "a.md", "score": 0.5, "metadata": {}}]
        answer = _render_retrieved_answer("q", chunks, None)
        excerpt = answer.split("Sources:")[0]
        for line in excerpt.splitlines():
            if line.startswith("|"):
                assert line.endswith("|"), f"partial table row leaked: {line!r}"

    def test_cut_inside_code_fence_is_closed(self) -> None:
        """The TEP CMS golden-path bug: the doc wraps its step list in a ```
        fence, the excerpt cut landed before the closing ```, and every later
        section — our own headings and tables included — rendered inside one
        giant code block. A cut excerpt must never leave a fence open."""
        # Blank line INSIDE the fence, like the real doc's step groups — that
        # is what makes the paragraph-boundary cut land mid-fence.
        steps_head = "\n".join(f"{i}. Langkah {i}         → Modul {i}" for i in range(1, 8))
        steps_tail = "\n".join(f"{i}. Langkah {i}         → Modul {i}" for i in range(8, 30))
        fenced = (
            "Ini urutan yang membuat semua fitur nyambung.\n\n```\n"
            + steps_head
            + "\n\n"
            + steps_tail
            + "\n```\n\nParagraf penutup."
        )
        chunks = [
            {"text": fenced, "source": "a.md", "score": 0.8, "metadata": {}},
            {
                "text": "| A | B |\n|---|---|\n| 1 | 2 |",
                "source": "b.md",
                "score": 0.7,
                "metadata": {"heading_path": "Bagian Kedua"},
            },
        ]
        answer = _render_retrieved_answer("q", chunks, None)
        assert answer.count("```") % 2 == 0
        # The next section's heading must sit OUTSIDE the fence — i.e. the
        # fence closes before it, not after.
        assert answer.index("```", answer.index("```") + 3) < answer.index("### 2. Bagian Kedua")

    def test_chunk_arriving_with_unclosed_fence_is_closed(self) -> None:
        """The indexer splits documents on headings, so a chunk can END inside
        a fence it opened — unbalanced before we ever cut it."""
        chunks = [
            {"text": "Contoh:\n\n```\npnpm dev", "source": "a.md", "score": 0.8, "metadata": {}}
        ]
        answer = _render_retrieved_answer("q", chunks, None)
        assert answer.count("```") % 2 == 0

    def test_crlf_line_endings_are_normalized(self) -> None:
        """The corpus is indexed on Windows, so chunk text can arrive with
        \\r\\n. Those must never reach the FE: marked drops a CRLF table to
        raw per-row paragraphs, and _excerpt's paragraph-boundary search
        ("\\n\\n") never matches, so cuts degrade to word boundaries."""
        table = "| A | B |\r\n|---|---|\r\n" + "\r\n".join(
            f"| baris {i} | nilai {i} |" for i in range(60)
        )
        chunks = [{"text": table, "source": "a.md", "score": 0.5, "metadata": {}}]
        answer = _render_retrieved_answer("q", chunks, None)
        assert "\r" not in answer
        for line in answer.split("Sources:")[0].splitlines():
            if line.startswith("|"):
                assert line.endswith("|"), f"partial table row leaked: {line!r}"

    def test_chunk_leading_heading_is_not_duplicated(self) -> None:
        """The chunk's first line is the same title we already print from
        heading_path; keeping it rendered every section title twice."""
        chunks = [
            {
                "text": "## Cara Membaca Dokumen Ini\n\nIsi bagian ini.",
                "source": "a.md",
                "score": 0.5,
                "metadata": {"heading_path": "TEP CMS > Cara Membaca Dokumen Ini"},
            }
        ]
        answer = _render_retrieved_answer("q", chunks, None)
        assert answer.count("Cara Membaca Dokumen Ini") == 1
        assert "Isi bagian ini." in answer

    def test_nothing_relevant_is_an_honest_dead_end(self) -> None:
        """No chunks cleared the floor: say so and suggest a next step, rather
        than quoting whatever came back."""
        answer = _render_nothing_relevant("cara deploy", "index is empty")
        assert "Belum bisa dijawab sekarang" in answer
        assert "cara deploy" in answer
        assert "index is empty" in answer
        assert "Sources:" not in answer
