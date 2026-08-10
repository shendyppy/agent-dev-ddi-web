"""Capture a screenshot of the Acelents site via Playwright.

Two trigger paths — exactly one must be supplied (validated on the input model):

- ``scenario`` — a named canonical page (``home``, ``tour``, ``plan-a-demo``,
  ``blog``). Maps 1:1 to a test in ``packages/e2e/tests/scenarios/``. Run via
  ``just screenshot <scenario>``.
- ``url`` — any path or absolute URL on the site (``/tour``,
  ``https://dev.acelents.com/x``). Captured on demand via
  ``just screenshot-url <url> <slug>`` and cached per URL.

Either way the PNG lands under the screenshot dir (served by FastAPI at
``/screenshots``) and we return the absolute URL the agent embeds as a markdown
image. See ADR 0008 for why screenshots flow as image URLs, not a new SSE event.

Conventions honoured (see ``mcp_servers/AGENTS.md``):

- **No ``agent.*`` imports.** MCP servers run as standalone subprocesses; we
  read config from ``os.environ`` and compute paths from ``__file__`` so they
  match the orchestrator's defaults without importing settings.
- **Errors as structured JSON, not exceptions through MCP.`` ``handle`` returns
  a ``{"error", "code"}`` dict on capture failure so the LLM can self-correct,
  matching the recovery contract in ``graph.call_tools``.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

# Repo root from this file: apps/backend/src/mcp_servers/<name>/handler.py.
# Same physical dir as agent.settings.REPO_ROOT — recomputed here because MCP
# servers must not import agent modules (AGENTS.md rule).
REPO_ROOT = Path(__file__).resolve().parents[5]

# Where Playwright writes PNGs and FastAPI serves them. Must equal the
# orchestrator's settings.screenshot_dir. Defaults are identical (absolute,
# repo-rooted) so backend-mount and handler-subprocess agree with zero config.
# NOTE: set via the OS environment, not .env — the .env file is not propagated
# to the MCP subprocess, so a .env-only value would reach the backend but not
# here, causing a serve/write mismatch.
SCREENSHOT_DIR = Path(os.environ.get("SCREENSHOT_DIR") or str(REPO_ROOT / ".data" / "screenshots"))
SCREENSHOT_BASE_URL = os.environ.get("SCREENSHOT_BASE_URL", "http://localhost:8000")


class ScreenshotInput(BaseModel):
    """Exactly one of ``scenario`` / ``url`` must be supplied."""

    scenario: str | None = Field(
        default=None,
        description='Named canonical page: "home", "tour", "plan-a-demo", or "blog".',
    )
    url: str | None = Field(
        default=None,
        description="Any route on the site, e.g. '/tour', or an absolute URL.",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> ScreenshotInput:
        if bool(self.scenario) == bool(self.url):
            raise ValueError("Provide exactly one of `scenario` or `url`.")
        return self


class ScreenshotOutput(BaseModel):
    screenshot_url: str
    scenario: str
    cached: bool
    source: str  # "scenario" | "url"


# Named scenario → PNG path under SCREENSHOT_DIR. Single source of truth for
# which canonical pages exist; keep in sync with tests/scenarios/*.spec.ts.
SCENARIO_PATHS: dict[str, str] = {
    "home": "home.png",
    "tour": "tour.png",
    "plan-a-demo": "plan-a-demo.png",
    "blog": "blog.png",
}


def _slugify_url(url: str) -> str:
    """Turn a route/URL into a stable, filesystem-safe slug.

    ``"/tour"`` → ``tour``; ``"/blog/my-post"`` → ``blog-my-post``; strips
    scheme/host and query. Same shape as ``indexing._slugify`` (lowercase +
    hyphenate) so on-demand filenames stay deterministic across calls.
    """
    path = re.sub(r"^[a-z]+://[^/]+", "", url, flags=re.IGNORECASE)
    path = path.split("?", 1)[0].split("#", 1)[0].strip("/")
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return slug or "root"


def _public_url(rel: str) -> str:
    """Absolute /screenshots URL the browser will fetch (FE is on another port)."""
    base = SCREENSHOT_BASE_URL.rstrip("/")
    return f"{base}/screenshots/{rel.lstrip('/')}"


async def _run(cmd: list[str]) -> tuple[int, str]:
    """Run a subprocess and return (returncode, combined stdout+stderr text)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    text = (stderr.decode(errors="replace") + "\n" + stdout.decode(errors="replace")).strip()
    return proc.returncode or 0, text


async def handle(payload: ScreenshotInput) -> ScreenshotOutput | dict[str, str]:
    """Capture (or reuse) a screenshot and return its public URL.

    Returns ``ScreenshotOutput`` on success, or ``{"error", "code"}`` on a
    capture failure — never raises through MCP. ``cached`` reflects whether the
    PNG already existed before this call (the per-scenario / per-URL cache).
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    if payload.scenario:
        scenario = payload.scenario.strip()
        rel = SCENARIO_PATHS.get(scenario, f"{scenario}.png")
        target = SCREENSHOT_DIR / rel
        cached = target.exists()
        if not cached:
            code, text = await _run(["just", "screenshot", scenario])
            if code != 0 or not target.exists():
                return {
                    "error": (
                        f"capture failed for scenario {scenario!r} (exit {code}): {text[-500:]}"
                    ),
                    "code": "capture_failed",
                }
        return ScreenshotOutput(
            screenshot_url=_public_url(rel),
            scenario=scenario,
            cached=cached,
            source="scenario",
        )

    # url path — narrowed by the input validator; the assert keeps mypy honest.
    assert payload.url
    slug = _slugify_url(payload.url)
    rel = f"_ondemand/{slug}.png"
    target = SCREENSHOT_DIR / rel
    cached = target.exists()
    if not cached:
        code, text = await _run(["just", "screenshot-url", payload.url, slug])
        if code != 0 or not target.exists():
            return {
                "error": f"capture failed for url {payload.url!r} (exit {code}): {text[-500:]}",
                "code": "capture_failed",
            }
    return ScreenshotOutput(
        screenshot_url=_public_url(rel),
        scenario=slug,
        cached=cached,
        source="url",
    )
