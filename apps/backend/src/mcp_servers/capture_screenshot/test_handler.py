"""Unit tests for capture_screenshot.handler.

Playwright itself is never launched here — ``_run`` (the subprocess call into
``just screenshot``) is monkeypatched, and the screenshot dir is redirected to a
tmp path. What we exercise is the routing, caching, URL building, and the
structured-error contract.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mcp_servers.capture_screenshot import handler as h
from mcp_servers.capture_screenshot.handler import (
    ScreenshotInput,
    ScreenshotOutput,
    _public_url,
    _slugify_url,
    handle,
)

# ─── pure helpers ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/tour", "tour"),
        ("/blog/my-post", "blog-my-post"),
        ("https://dev.acelents.com/plan-a-demo", "plan-a-demo"),
        ("/", "root"),
        ("/Tour/?x=1#frag", "tour"),
        ("", "root"),
    ],
)
def test_slugify_url(url: str, expected: str) -> None:
    assert _slugify_url(url) == expected


def test_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h, "SCREENSHOT_BASE_URL", "http://localhost:8000")
    assert _public_url("tour.png") == "http://localhost:8000/screenshots/tour.png"
    assert _public_url("_ondemand/blog-x.png") == (
        "http://localhost:8000/screenshots/_ondemand/blog-x.png"
    )
    # Trailing slash on base + leading slash on rel must not double up.
    monkeypatch.setattr(h, "SCREENSHOT_BASE_URL", "http://h:8000/")
    assert _public_url("/x.png") == "http://h:8000/screenshots/x.png"


# ─── input validation ───────────────────────────────────────────────────


def test_input_requires_exactly_one() -> None:
    with pytest.raises(ValueError):
        ScreenshotInput()
    with pytest.raises(ValueError):
        ScreenshotInput(scenario="home", url="/tour")
    # One of each is valid:
    assert ScreenshotInput(scenario="home").scenario == "home"
    assert ScreenshotInput(url="/tour").url == "/tour"


# ─── handle() routing / caching / errors ────────────────────────────────


def _stub_run(captured: dict, *, code: int = 0, text: str = "", create_file: bool = True):
    """Build a fake _run that records the command and optionally writes the PNG."""

    async def fake_run(cmd: list[str]) -> tuple[int, str]:
        captured["cmd"] = cmd
        if create_file and code == 0:
            # Reproduce what Playwright would do: write the target PNG.
            # Target path comes from the cmd shape:
            #   screenshot <name>     -> <dir>/<SCENARIO_PATHS>
            #   screenshot-url <slug> -> <dir>/_ondemand/<slug>.png
            target = _target_for(cmd, h.SCREENSHOT_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"PNG")
        return code, text

    return fake_run


def _target_for(cmd: list[str], root: Path) -> Path:
    if cmd[1:2] == ["screenshot-url"]:
        slug = cmd[-1]
        return root / "_ondemand" / f"{slug}.png"
    name = cmd[-1]
    return root / h.SCENARIO_PATHS.get(name, f"{name}.png")


def test_scenario_cache_hit_skips_playwright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(h, "SCREENSHOT_DIR", tmp_path)
    (tmp_path / "tour.png").write_bytes(b"PNG")  # pre-cached

    captured: dict = {}
    monkeypatch.setattr(h, "_run", _stub_run(captured, create_file=False))

    out = asyncio.run(handle(ScreenshotInput(scenario="tour")))

    assert isinstance(out, ScreenshotOutput)
    assert out.cached is True
    assert out.source == "scenario"
    assert out.scenario == "tour"
    assert out.screenshot_url.endswith("/screenshots/tour.png")
    assert "cmd" not in captured  # _run must not be called on a cache hit


def test_scenario_capture_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h, "SCREENSHOT_DIR", tmp_path)
    captured: dict = {}
    monkeypatch.setattr(h, "_run", _stub_run(captured))

    out = asyncio.run(handle(ScreenshotInput(scenario="home")))

    assert isinstance(out, ScreenshotOutput)
    assert out.cached is False
    assert out.screenshot_url.endswith("/screenshots/home.png")
    assert captured["cmd"] == ["just", "screenshot", "home"]


def test_scenario_capture_failure_returns_structured_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(h, "SCREENSHOT_DIR", tmp_path)
    monkeypatch.setattr(h, "_run", _stub_run({}, code=1, text="browser not found"))

    out = asyncio.run(handle(ScreenshotInput(scenario="home")))

    assert isinstance(out, dict)
    assert out["code"] == "capture_failed"
    assert "home" in out["error"]
    assert "browser not found" in out["error"]


def test_url_capture_success_uses_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h, "SCREENSHOT_DIR", tmp_path)
    captured: dict = {}
    monkeypatch.setattr(h, "_run", _stub_run(captured))

    out = asyncio.run(handle(ScreenshotInput(url="/blog/my-post")))

    assert isinstance(out, ScreenshotOutput)
    assert out.source == "url"
    assert out.scenario == "blog-my-post"  # slug
    assert out.screenshot_url.endswith("/screenshots/_ondemand/blog-my-post.png")
    assert captured["cmd"] == ["just", "screenshot-url", "/blog/my-post", "blog-my-post"]


def test_url_cache_hit_skips_playwright(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h, "SCREENSHOT_DIR", tmp_path)
    (tmp_path / "_ondemand").mkdir()
    (tmp_path / "_ondemand" / "tour.png").write_bytes(b"PNG")

    monkeypatch.setattr(h, "_run", _stub_run({}, create_file=False))

    out = asyncio.run(handle(ScreenshotInput(url="/tour")))

    assert isinstance(out, ScreenshotOutput)
    assert out.cached is True
    assert out.source == "url"
