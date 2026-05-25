---
name: capture_screenshot
version: 1
inputs:
  scenario: "string — Playwright test name (matches `--grep` pattern)"
outputs:
  screenshot_url: "string — public URL or local file path"
  scenario: "string — echoed back"
when_to_use: |
  Call when the user asks for visual evidence of a feature ("show me",
  "screenshot of", "what does X look like"), or when describing a UI in
  words would be longer/less useful than a picture.
---

# capture_screenshot

Invokes Playwright via the e2e package to run a named scenario and capture a screenshot.
Scenario names match `--grep` patterns of tests in `packages/e2e/tests/`.

Scenarios are listed per-product in `docs/product-catalog.md`.
