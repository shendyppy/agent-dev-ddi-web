---
id: plan-a-demo
name: Plan a Demo
product_id: acelents
requires_auth: false
access_path: /plan-a-demo
screenshot_scenarios:
  - plan-a-demo
---

# Plan a Demo

## What it does

Lead-capture form where a prospective customer requests a personalized demo.
Submissions route to the sales pipeline.

## How to access

1. Go to https://dev.acelents.com/plan-a-demo
   (or click "Plan a Demo" from the home page).

## Required permissions

None to view. Submission is open to any visitor.

## Edge cases

- Form validation messages only render after an invalid submit; capture the
  empty form for the canonical scenario.
- Do not submit real PII during a capture run.

## Screenshot scenarios

- `plan-a-demo` — full-page capture of the demo-request form
  (`packages/e2e/tests/scenarios/plan-a-demo.spec.ts`)

## Related features

- [Home](home.md)
- [Product Tour](tour.md)
