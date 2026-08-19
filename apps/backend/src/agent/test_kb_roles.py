"""Tests for the Supabase role lookup.

Everything here is really one property: a lookup that cannot answer must
return None, never raise and never guess. `None` sends the caller to the
bootstrap seed and then to "not a maintainer", so a flaky network downgrades
someone's publishing rights for one request — it never grants them, and it
never takes down submitting, which needs no role at all.
"""

from __future__ import annotations

from typing import Any

import pytest

from . import kb_roles
from .kb_roles import fetch_role


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _client_returning(response: _FakeResponse | Exception) -> Any:
    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def get(self, *_: Any, **__: Any) -> _FakeResponse:
            if isinstance(response, Exception):
                raise response
            return response

    return FakeClient


@pytest.fixture(autouse=True)
def supabase_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kb_roles.settings, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(kb_roles.settings, "supabase_anon_key", "anon-key")


class TestRoleIsReturned:
    async def test_a_matching_row_yields_its_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            kb_roles.httpx,
            "AsyncClient",
            _client_returning(_FakeResponse(200, [{"role": "maintainer"}])),
        )

        assert await fetch_role("budi@example.com", "token") == "maintainer"

    async def test_the_role_is_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            kb_roles.httpx,
            "AsyncClient",
            _client_returning(_FakeResponse(200, [{"role": " Maintainer "}])),
        )

        assert await fetch_role("budi@example.com", "token") == "maintainer"


class TestUnansweredLookupsReturnNone:
    async def test_no_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            kb_roles.httpx, "AsyncClient", _client_returning(_FakeResponse(200, []))
        )

        assert await fetch_role("nobody@example.com", "token") is None

    async def test_table_missing_is_not_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """404 before the migration has been applied. The bootstrap seed has to
        keep working against a database where kb_roles does not exist yet."""
        monkeypatch.setattr(
            kb_roles.httpx, "AsyncClient", _client_returning(_FakeResponse(404, None))
        )

        assert await fetch_role("budi@example.com", "token") is None

    async def test_rls_refusal_is_not_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            kb_roles.httpx, "AsyncClient", _client_returning(_FakeResponse(401, None))
        )

        assert await fetch_role("budi@example.com", "token") is None

    async def test_network_failure_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            kb_roles.httpx, "AsyncClient", _client_returning(kb_roles.httpx.ConnectError("boom"))
        )

        assert await fetch_role("budi@example.com", "token") is None

    async def test_unparseable_body_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            kb_roles.httpx,
            "AsyncClient",
            _client_returning(_FakeResponse(200, ValueError("not json"))),
        )

        assert await fetch_role("budi@example.com", "token") is None

    async def test_unconfigured_supabase_skips_the_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(kb_roles.settings, "supabase_url", "")

        def explode(**_: Any) -> None:
            raise AssertionError("should not have made a request")

        monkeypatch.setattr(kb_roles.httpx, "AsyncClient", explode)

        assert await fetch_role("budi@example.com", "token") is None
