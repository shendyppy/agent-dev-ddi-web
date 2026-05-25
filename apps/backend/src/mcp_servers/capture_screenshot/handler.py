"""Triggers Playwright runs in packages/e2e/."""

from __future__ import annotations

from pydantic import BaseModel


class ScreenshotInput(BaseModel):
    scenario: str


class ScreenshotOutput(BaseModel):
    screenshot_url: str
    scenario: str


async def handle(payload: ScreenshotInput) -> ScreenshotOutput:
    # TODO: subprocess into `just screenshot <scenario>` and resolve the
    # resulting artifact path. For now, return a placeholder.
    return ScreenshotOutput(
        screenshot_url=f"/screenshots/{payload.scenario}.png",
        scenario=payload.scenario,
    )
