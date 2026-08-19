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
from .kb_auth import _is_bootstrap_maintainer, require_kb_maintainer, require_kb_writer


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
    monkeypatch.setattr(kb_auth.settings, "kb_maintainer_emails", "")
    # No row unless a test says otherwise, so the default path is "not a
    # maintainer" rather than whatever the last test happened to leave behind.
    monkeypatch.setattr(kb_auth, "fetch_role", _role_returning(None))


def _role_returning(role: str | None):
    async def _fetch(_email: str, _token: str) -> str | None:
        return role

    return _fetch


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


class TestSubmittingNeedsNoRole:
    async def test_any_signed_in_user_may_submit(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Submissions are quarantined in the review inbox, so gating them
        would only deter contribution without protecting anything."""
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "siapa-saja@example.com"})),
        )

        assert await require_kb_writer(authorization="Bearer good") == "siapa-saja@example.com"


class TestBootstrapList:
    @pytest.mark.parametrize(
        ("email", "seed", "expected"),
        [
            # Empty matches NOBODY — the opposite of the old writer allowlist.
            # An unconfigured seed must not turn publishing into a free-for-all.
            ("a@b.com", "", False),
            ("a@b.com", "a@b.com", True),
            ("a@b.com", "c@d.com", False),
            ("a@company.com", "@company.com", True),
            ("a@other.com", "@company.com", False),
            ("a@b.com", "c@d.com, a@b.com", True),
        ],
    )
    def test_membership(
        self, email: str, seed: str, expected: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_auth.settings, "kb_maintainer_emails", seed)
        assert _is_bootstrap_maintainer(email) is expected

    async def test_the_seed_works_before_the_roles_table_exists(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chicken and egg: the first maintainer cannot be granted a row by
        anyone, so the seed is checked before the table is consulted."""
        monkeypatch.setattr(kb_auth.settings, "kb_maintainer_emails", "lead@example.com")
        monkeypatch.setattr(kb_auth, "fetch_role", _role_returning(None))
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "lead@example.com"})),
        )

        assert await require_kb_maintainer(authorization="Bearer good") == "lead@example.com"


class TestRoleFromSupabase:
    async def test_a_maintainer_row_grants_publishing(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_auth, "fetch_role", _role_returning("maintainer"))
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "budi@example.com"})),
        )

        assert await require_kb_maintainer(authorization="Bearer good") == "budi@example.com"

    async def test_a_writer_row_does_not_grant_publishing(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_auth, "fetch_role", _role_returning("writer"))
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "budi@example.com"})),
        )

        with pytest.raises(HTTPException) as excinfo:
            await require_kb_maintainer(authorization="Bearer good")

        assert excinfo.value.status_code == 403

    async def test_no_row_and_no_seed_cannot_publish(
        self, supabase_configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Publishing fails closed. Submitting still works for the same user —
        that asymmetry is the whole design."""
        monkeypatch.setattr(
            kb_auth.httpx,
            "AsyncClient",
            _fake_client(_FakeResponse(200, {"email": "junior@example.com"})),
        )

        assert await require_kb_writer(authorization="Bearer good") == "junior@example.com"
        with pytest.raises(HTTPException) as excinfo:
            await require_kb_maintainer(authorization="Bearer good")
        assert excinfo.value.status_code == 403
        assert "grant the role" in str(excinfo.value.detail)
