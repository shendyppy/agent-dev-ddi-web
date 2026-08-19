"""Tests for dev port resolution and the settings that have to follow it.

The bug these exist for: `just dev` hardcoded --port 8000, another project
already owned 8000, uvicorn died with [Errno 10048] while the frontend stayed
up, and the browser spent the session talking to a foreign service. That
service's 404s arrived without an Access-Control-Allow-Origin header, so the
browser reported CORS and the real cause never surfaced.
"""

from __future__ import annotations

import socket

import pytest

from .devserver import is_port_free, resolve_port
from .settings import Settings


@pytest.fixture
def held_port() -> int:
    """A port with a real listener on it, released when the test ends."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        yield sock.getsockname()[1]


class TestPortProbe:
    def test_a_held_port_reads_as_busy(self, held_port: int) -> None:
        assert is_port_free(held_port) is False

    def test_an_unheld_port_reads_as_free(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        # Socket closed above, so the port is free again.
        assert is_port_free(port) is True


class TestResolvePort:
    def test_preferred_port_is_kept_when_free(self) -> None:
        """The ordinary case must not drift. Only a collision moves the port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            free = sock.getsockname()[1]

        assert resolve_port(free) == free

    def test_a_taken_port_is_stepped_over(self, held_port: int) -> None:
        """The exact scenario: something else already owns the port we wanted."""
        resolved = resolve_port(held_port)

        assert resolved != held_port
        assert resolved > held_port

    def test_exhausting_the_span_raises_instead_of_guessing(self, held_port: int) -> None:
        """A span of 1 over a held port has nowhere to go. Better to fail loudly
        than to bind something surprising."""
        with pytest.raises(RuntimeError, match="no free TCP port"):
            resolve_port(held_port, span=1)


class TestScreenshotBaseUrlFollowsPort:
    def test_default_tracks_backend_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Screenshots are embedded as absolute URLs in the agent's answers, so
        a stale :8000 renders as a broken image inside a chat reply — a symptom
        that looks nothing like a port problem."""
        monkeypatch.setenv("BACKEND_PORT", "8123")
        monkeypatch.delenv("SCREENSHOT_BASE_URL", raising=False)

        settings = Settings()

        assert settings.backend_port == 8123
        assert settings.screenshot_base_url == "http://localhost:8123"

    def test_explicit_value_still_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Deployments behind a proxy set this by hand; the default must not
        overwrite them."""
        monkeypatch.setenv("BACKEND_PORT", "8123")
        monkeypatch.setenv("SCREENSHOT_BASE_URL", "https://docs.internal.example")

        settings = Settings()

        assert settings.screenshot_base_url == "https://docs.internal.example"
