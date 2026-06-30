---
id: tour
name: Product Tour
product_id: acelents
requires_auth: false
access_path: /tour
screenshot_scenarios:
  - tour
---

# Product Tour

## What it does

Guided walkthrough of the Acelents product. Steps the visitor through the key
flows so they understand the value before requesting a demo.

## How to access

1. Go to https://dev.acelents.com/tour
   (or click "Tour" from the home page nav).

## Required permissions

None. Public page.

## Edge cases

- Tour steps animate in sequence; a full-page capture shows the page shell,
  not a specific step. To capture a specific step, use an on-demand
  `capture_screenshot(url=...)` after navigating to that step.

## Screenshot scenarios

- `tour` — full-page capture of the tour page
  (`packages/e2e/tests/scenarios/tour.spec.ts`)

## Related features

- [Home](home.md)
- [Plan a Demo](plan-a-demo.md)
