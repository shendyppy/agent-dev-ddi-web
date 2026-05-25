---
id: example-feature
name: Example Feature
product_id: _template
requires_auth: false
access_path: /example
screenshot_scenarios:
  - template-example-feature
---

# Example Feature

## What it does

1-2 sentences from the user's perspective. Their goal, not the implementation.

## How to access

Step-by-step from a fresh session:

1. Open http://localhost:3000
2. Click "Example" in the nav
3. See the example feature page

## Required permissions

None. (Or: "Admin role", or "Feature flag `example_enabled`".)

## Edge cases

- What happens when the user is not logged in
- What happens on validation errors
- Any rate limits or quirks

## Screenshot scenarios

- `template-example-feature` — captures the example feature page (in `packages/e2e/tests/scenarios/template-example-feature.spec.ts`)

## Related features

- (link to other features here)
