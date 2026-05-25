# packages/e2e — AGENTS.md

Playwright suite used for two distinct purposes:

1. **Smoke tests** for the agent's own UI (chat works, MCP roundtrip works).
2. **Evidence capture** — scenarios that the `capture_screenshot` MCP skill triggers to produce screenshots for the chatbot to return to users.

These two purposes share the same Playwright config but live in different test folders for clarity.

## Layout

```
tests/
├── smoke/             ← runs in CI on every PR
└── scenarios/         ← named scenarios invoked by capture_screenshot skill
```

## Adding a screenshot scenario

1. Create `tests/scenarios/<scenario-name>.spec.ts`.
2. The test name must match exactly — it's what the agent passes as `--grep`.
3. Call `await page.screenshot({ path: 'evidence/<scenario>.png', fullPage: true })`.
4. List the scenario in the product's entry under `docs/product-catalog.md`.

## Rules

- **Each scenario is self-contained.** No shared fixtures across scenarios — the agent invokes them one at a time.
- **No flaky waits.** Use `page.waitForSelector` / `page.waitForResponse`, never `setTimeout`.
- **Screenshots go to `evidence/`** — served back through the backend so the chat UI can render them.

## Running

```powershell
just test-e2e                        # full suite
just screenshot <scenario-name>      # one scenario (invoked by skill, but useful for debugging)
```
