---
name: capture_screenshot
version: 2
inputs:
  scenario: 'string (optional) — named canonical page: "home", "tour", "plan-a-demo", "blog"'
  url: 'string (optional) — any route on the site ("/tour") or an absolute URL'
outputs:
  screenshot_url: 'string — absolute URL of the captured PNG (served at /screenshots)'
  scenario: 'string — the scenario name, or the slug derived from url'
  cached: 'boolean — true if a previously captured PNG was reused'
  source: 'string — "scenario" | "url"'
  error: 'string (only on failure) — what went wrong'
  code: 'string (only on failure) — "capture_failed" | "invalid_input"'
when_to_use: |
  Call when the user asks for visual evidence ("show me", "screenshot of",
  "what does X look like", "tunjukkan halaman X"), or when describing a UI in
  words would be longer or less useful than a picture. Provide exactly one of
  `scenario` (for the canonical pages above) or `url` (for any other route on
  the site). Captures are cached per scenario/URL, so repeat calls are cheap.
---

# capture_screenshot

Invokes Playwright (via `just screenshot` / `just screenshot-url`) to navigate
the live Acelents site at https://dev.acelents.com and capture a full-page PNG.
The PNG is written under the backend's screenshot dir and served at
`/screenshots`, so the returned `screenshot_url` is fetchable by the browser.

## How to use the result

**Always embed the `screenshot_url` as a markdown image in your answer** so the
user sees it inline — never paste the raw URL as text:

```markdown
![Halaman Tour](http://localhost:8000/screenshots/tour.png)
```

If the tool returns `{"error": ...}`, tell the user briefly what failed (e.g.
unknown page name, site unreachable) and offer to try a different route.

## Canonical scenarios

Map 1:1 to tests in `packages/e2e/tests/scenarios/`. Keep this list in sync
with `handler.SCENARIO_PATHS`:

| scenario | route |
|---|---|
| `home` | `/` |
| `tour` | `/tour` |
| `plan-a-demo` | `/plan-a-demo` |
| `blog` | `/blog` |

For any other route, pass `url` instead (e.g. `url="/blog/some-post"`).
