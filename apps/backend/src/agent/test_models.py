"""Tests for the model catalogue and the credential guards around it.

These are the ADR 0010 safety properties. All three fail silently in production
if they regress — a leaked key does not raise, and an unenforced allowlist looks
identical to an enforced one until someone points the header somewhere else.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from . import models as models_module
from . import server as server_module
from .server import _redact, app


class TestDerivedCatalogue:
    """The catalogue is derived from `litellm.model_cost`, not hand-written.
    These lock the filter that makes it safe to hand to a picker."""

    def test_every_recommendation_actually_exists(self) -> None:
        """The regression that motivated deriving in the first place: the
        hand-written list shipped two model ids that do not exist
        (`openrouter/deepseek/deepseek-chat`, `openrouter/qwen/qwen3-32b`).
        Nothing caught it, because nothing was checking."""
        ids = {e["id"] for e in models_module._usable_models()}
        missing = [m for m in models_module.RECOMMENDED if m not in ids]
        assert not missing, f"recommended but not in the registry: {missing}"

    def test_every_entry_supports_tool_calling(self) -> None:
        """The hard requirement. A model without it does not answer worse — it
        answers with no retrieval at all."""
        import litellm

        for entry in models_module._usable_models():
            spec = litellm.model_cost[entry["id"]]
            assert spec.get("supports_function_calling"), entry["id"]

    def test_non_chat_modes_are_excluded(self) -> None:
        """Embedding and image models cannot hold a conversation."""
        import litellm

        for entry in models_module._usable_models():
            assert litellm.model_cost[entry["id"]].get("mode") == "chat"

    def test_deprecated_models_are_excluded(self) -> None:
        import datetime

        import litellm

        today = datetime.date.today().isoformat()
        for entry in models_module._usable_models():
            dep = litellm.model_cost[entry["id"]].get("deprecation_date")
            assert not dep or str(dep) >= today, entry["id"]

    def test_only_providers_we_can_credential_appear(self) -> None:
        """Bedrock and Vertex need multi-part credentials a single API key
        cannot express (ADR 0010), so offering them would be offering a
        guaranteed failure."""
        for entry in models_module._usable_models():
            assert entry["provider"] in models_module.SUPPORTED_PROVIDERS

    def test_recommendations_are_pinned_first(self) -> None:
        entries = models_module._usable_models()
        first = [e["id"] for e in entries[: len(models_module.RECOMMENDED)]]
        assert set(first) == set(models_module.RECOMMENDED)

    def test_the_list_is_substantial(self) -> None:
        """A guard against the filter silently over-narrowing — if a future
        registry change breaks a field name, this fails instead of quietly
        leaving the picker nearly empty."""
        assert len(models_module._usable_models()) > 50


class TestIsAllowed:
    """The picker is a UI affordance; this is the enforcement. Without it,
    `X-Model-Id` would let any caller aim the backend at an arbitrary provider
    using the server's own credentials — the same reasoning as ADR 0009's
    "a prompt is not an access control", applied to a header."""

    def test_catalogue_entries_pass(self) -> None:
        assert models_module.is_allowed("deepseek/deepseek-chat")

    def test_unknown_model_is_rejected(self) -> None:
        assert not models_module.is_allowed("some-random/model")

    def test_configured_default_always_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A deployment must be able to pin a model that is not in the catalogue
        without locking itself out of its own chat endpoint."""
        monkeypatch.setattr(models_module.settings, "litellm_model", "custom/private-model")
        assert models_module.is_allowed("custom/private-model")

    def test_empty_string_is_not_a_free_pass(self) -> None:
        assert not models_module.is_allowed("")


class TestRedact:
    """The SSE error path forwards provider exception strings to the browser
    verbatim. Those strings are built by code we do not control."""

    def test_removes_the_key(self) -> None:
        assert "sk-secret-value" not in _redact(
            "auth failed for sk-secret-value", "sk-secret-value"
        )

    def test_leaves_text_alone_when_there_is_no_key(self) -> None:
        assert _redact("RateLimitError: 429", None) == "RateLimitError: 429"

    def test_ignores_implausibly_short_secrets(self) -> None:
        """A 3-character 'key' would redact ordinary words out of the message and
        make real errors unreadable. Nothing that short is a real credential."""
        assert _redact("error at api endpoint", "api") == "error at api endpoint"

    @pytest.mark.parametrize(
        "leaked",
        [
            "sk-proj-abcdefghijklmnopqrstuvwx",
            "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q",
            "gsk-abcdefghijklmnopqrst",
            "Authorization: Bearer abcdefghijklmnopqrst",
        ],
    )
    def test_redacts_keys_it_was_never_told_about(self, leaked: str) -> None:
        """The caller's key is not the only one that can reach an error string.
        A provider SDK can echo the SERVER's key back just as easily, and this
        function has no list of those to compare against — they live in
        os.environ under any of 141 possible names."""
        out = _redact(f"AuthenticationError: rejected {leaked}", None)
        assert leaked not in out
        assert "***redacted***" in out

    def test_does_not_scrub_ordinary_diagnostics(self) -> None:
        """Redacting anything long and random would make real failures
        undebuggable — one blind spot traded for another."""
        msg = "GraphRecursionError at session 3fbffebe-25d6-43c4-9071-a28482433352"
        assert _redact(msg, None) == msg


class TestModelsEndpoint:
    """`available` must agree with what will happen at send time, and must never
    hand the caller's own key back to them."""

    @pytest.fixture(autouse=True)
    def _no_ambient_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # litellm's import-time load_dotenv() loads the real .env, so without
        # this the assertions would depend on which keys this machine happens
        # to have.
        for var in (
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(models_module.settings, "model_api_key", None)

    def test_nothing_is_available_without_credentials(self) -> None:
        payload = models_module.available()
        assert all(not m["available"] for m in payload)
        assert all(m["source"] == "none" for m in payload)

    def test_a_server_key_is_reported_as_server_sourced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "server-side")
        entry = next(m for m in models_module.available() if m["id"].startswith("gemini/"))
        assert entry["source"] == "server"
        assert entry["available"]

    def test_user_key_entries_are_marked_as_theirs_not_guaranteed(self) -> None:
        """The distinction that stops a footgun. A pasted key belongs to ONE
        provider and nothing in it reliably says which, so every entry the
        server cannot vouch for is labelled `your-key` rather than being
        presented as though it will definitely work."""
        payload = models_module.available("sk-or-user-key")
        assert all(m["available"] for m in payload)
        assert all(m["source"] == "your-key" for m in payload)

    def test_server_key_wins_over_the_user_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Where the deployment can authenticate, say so — that entry is a
        promise, not a hope, and the user's key is not spent on it."""
        monkeypatch.setenv("GEMINI_API_KEY", "server-side")
        payload = models_module.available("sk-or-user-key")
        gemini = next(m for m in payload if m["id"].startswith("gemini/"))
        openrouter = next(m for m in payload if m["id"].startswith("openrouter/"))
        assert gemini["source"] == "server"
        assert openrouter["source"] == "your-key"

    def test_blank_user_key_does_not_unlock_anything(self) -> None:
        assert all(m["source"] == "none" for m in models_module.available("   "))

    def test_response_never_echoes_the_key(self) -> None:
        secret = "sk-or-must-not-come-back"
        client = TestClient(app)
        response = client.get("/api/models", headers={"X-Model-Api-Key": secret})
        assert response.status_code == 200
        assert secret not in response.text
        # …but it was used, or the availability flags would be meaningless.
        assert any(m["available"] for m in response.json()["models"])

    def test_response_names_the_variable_to_set(self) -> None:
        """An unavailable entry should tell the user which key to go and get,
        not just refuse."""
        payload = models_module.available()
        assert all(m["env_key"] for m in payload)


class TestChatRejectsUnknownModels:
    def test_disallowed_header_is_a_400(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "halo"}]},
            headers={"X-Model-Id": "evil/model"},
        )
        assert response.status_code == 400
        assert "not allowed" in response.text

    def test_no_header_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The pre-BYOK path must be untouched: no headers means the deployment's
        own configuration, exactly as before."""
        captured: dict[str, object] = {}

        def _fake_stream(initial_state: dict[str, object], session_id: str):  # type: ignore[no-untyped-def]
            captured.update(initial_state)

            async def _gen():  # type: ignore[no-untyped-def]
                yield {"event": "done", "data": session_id}

            return _gen()

        monkeypatch.setattr(server_module, "_stream_graph_events", _fake_stream)
        client = TestClient(app)
        response = client.post(
            "/api/chat", json={"messages": [{"role": "user", "content": "halo"}]}
        )
        assert response.status_code == 200
        assert captured["model"] is None
        assert captured["api_key"] is None
        assert captured["offline"] is False


class TestOfflineHeader:
    """Offline mode is per REQUEST, not per process. `settings.llm_fake_mode` is
    module-global, so a UI button wired to it would let one person switch the
    model off for everyone sharing the deployment."""

    def _capture(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
        captured: dict[str, object] = {}

        def _fake_stream(initial_state: dict[str, object], session_id: str):  # type: ignore[no-untyped-def]
            captured.update(initial_state)

            async def _gen():  # type: ignore[no-untyped-def]
                yield {"event": "done", "data": session_id}

            return _gen()

        monkeypatch.setattr(server_module, "_stream_graph_events", _fake_stream)
        return captured

    def _post(self, header: str | None) -> dict[str, str]:
        return {"X-Offline-Mode": header} if header is not None else {}

    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("true", True),
            ("TRUE", True),
            ("  true  ", True),
            # The two things someone turning it OFF most plausibly writes. A
            # bare truthiness check would read both as on.
            ("false", False),
            ("0", False),
            ("", False),
            (None, False),
        ],
    )
    def test_only_explicit_true_enables_offline(
        self, monkeypatch: pytest.MonkeyPatch, header: str | None, expected: bool
    ) -> None:
        captured = self._capture(monkeypatch)
        client = TestClient(app)
        response = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "halo"}]},
            headers=self._post(header),
        )
        assert response.status_code == 200
        assert captured["offline"] is expected
