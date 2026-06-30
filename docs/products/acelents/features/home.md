---
id: home
name: Home
product_id: acelents
requires_auth: false
access_path: /
screenshot_scenarios:
  - home
---

# Home

## What it does

The landing page — first thing a visitor sees. Introduces Acelents, surfaces
the primary calls-to-action (Tour, Plan a Demo), and routes into the rest of
the site.

## How to access

1. Go to https://dev.acelents.com/

## Required permissions

None. Public page.

## Edge cases

- Heavy hero animation on first paint — let `networkidle` settle before
  capturing (the Playwright scenario already does).

## Screenshot scenarios

- `home` — full-page capture of the landing page
  (`packages/e2e/tests/scenarios/home.spec.ts`)

## Related features

- [Product Tour](tour.md)
- [Plan a Demo](plan-a-demo.md)
