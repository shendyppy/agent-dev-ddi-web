---
id: blog
name: Blog
product_id: acelents
requires_auth: false
access_path: /blog
screenshot_scenarios:
  - blog
---

# Blog

## What it does

Listing of published posts plus individual post pages (`/blog/<slug>`). Drives
organic traffic and product narrative.

## How to access

1. Go to https://dev.acelents.com/blog for the listing.
2. Click any post to read it at `/blog/<slug>`.

## Required permissions

None. Public pages.

## Edge cases

- Individual posts are dynamic routes — there is no canonical scenario per
  post. Capture a specific post on demand with
  `capture_screenshot(url="/blog/<slug>")`.

## Screenshot scenarios

- `blog` — full-page capture of the blog listing
  (`packages/e2e/tests/scenarios/blog.spec.ts`)

## Related features

- [Home](home.md)
