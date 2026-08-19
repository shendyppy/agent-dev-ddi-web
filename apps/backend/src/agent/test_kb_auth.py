"""Tests for who may write documentation.

The endpoint these guard used to be completely unauthenticated: the frontend
hid the button behind `user &&`, which any curl ignores. Every test here is a
door that used to be open.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from . import kb_auth
from .kb_auth import _is_allowed, require_kb_maintainer, require_kb_writer


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


def _fake_client(response: _FakeResponse) -> Any:
    """Stand-in for httpx.AsyncClient used as an async context manager."""

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def get(self, *_: Any, **__: Any) -> _FakeResponse:
            return response

    return FakeClient


@pytest.fixture
def supabase_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kb_auth.settings, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(kb_auth.settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(kb_auth.settings, "kb_writer_emails", "")
    monkeypatch.setattr(kb_auth.settings, "kb_maintainer_emails", "")


class TestTokenIsRequired:
    async def test_missing_header_is_401(self, supabase_configured: None) -> None:
        with pytest.raises(HTTPException) as excinfo:
            await require_kb_writer(authorization=None)

        assert excinfo.value.status_code == 401

    async def test_non_bearer_scheme_is_401(self, supabase_configured: None) -> None:
        with pytest.raises(HTTPException) as excinfo:
            await require_kb_writer(authorization="Basic abc123")

        assert excinfo.value.status_code == 401

    async def test_rejected_token_is_401(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_auth.httpx, "AsyncClient", _fake_client(_FakeResponse(401)))

        with pytest.raises(HTTPException) as excinfo:
            await require_kb_writer(authorization="Bearer expired")

        assert excinfo.value.status_code == 401


class TestUnconfiguredAuthFailsClosed:
    async def test_missing_supabase_config_is_503_not_open_access(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unconfigured auth backend must never degrade into 'no auth'."""
        monkeypatch.setattr(kb_auth.settings, "supabase_url", "")
        monkeypatch.setattr(kb_auth.settings, "supabase_anon_key", "")

        with pytest.raises(HTTPException) as excinfo:
            await require_kb_writer(authorization="Bearer anything")

        assert excinfo.value.status_code == 503


class TestVerifiedIdentity:
    async def test_a_valid_token_resolves_to_a_lowercased_email(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "Shendy@Example.COM"})),
        )

        assert await require_kb_writer(authorization="Bearer good") == "shendy@example.com"

    async def test_an_unreachable_auth_service_is_503_not_401(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reporting a network problem as a rejected identity would send the
        user off to re-authenticate for no reason."""

        class ExplodingClient:
            def __init__(self, **_: Any) -> None:
                pass

            async def __aenter__(self) -> ExplodingClient:
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def get(self, *_: Any, **__: Any) -> None:
                raise kb_auth.httpx.ConnectError("boom")

        monkeypatch.setattr(kb_auth.httpx, "AsyncClient", ExplodingClient)

        with pytest.raises(HTTPException) as excinfo:
            await require_kb_writer(authorization="Bearer good")

        assert excinfo.value.status_code == 503


class TestAllowlist:
    @pytest.mark.parametrize(
        ("email", "allowlist", "expected"),
        [
            ("a@b.com", [], True),  # empty list = any signed-in user
            ("a@b.com", ["a@b.com"], True),
            ("a@b.com", ["c@d.com"], False),
            ("a@company.com", ["@company.com"], True),
            ("a@other.com", ["@company.com"], False),
            ("a@b.com", ["c@d.com", "a@b.com"], True),
        ],
    )
    def test_membership(self, email: str, allowlist: list[str], expected: bool) -> None:
        assert _is_allowed(email, allowlist) is expected

    async def test_writer_not_on_the_list_is_403(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_auth.settings, "kb_writer_emails", "someone-else@example.com")
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "outsider@example.com"})),
        )

        with pytest.raises(HTTPException) as excinfo:
            await require_kb_writer(authorization="Bearer good")

        assert excinfo.value.status_code == 403

    async def test_maintainer_falls_back_to_the_writer_list(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One list is enough for a small team; two only when they diverge."""
        monkeypatch.setattr(kb_auth.settings, "kb_writer_emails", "lead@example.com")
        monkeypatch.setattr(kb_auth.settings, "kb_maintainer_emails", "")
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "lead@example.com"})),
        )

        assert await require_kb_maintainer(authorization="Bearer good") == "lead@example.com"

    async def test_a_writer_is_not_automatically_a_maintainer(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_auth.settings, "kb_writer_emails", "@example.com")
        monkeypatch.setattr(kb_auth.settings, "kb_maintainer_emails", "lead@example.com")
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "junior@example.com"})),
        )

        assert await require_kb_writer(authorization="Bearer good") == "junior@example.com"
        with pytest.raises(HTTPException) as excinfo:
            await require_kb_maintainer(authorization="Bearer good")
        assert excinfo.value.status_code == 403
