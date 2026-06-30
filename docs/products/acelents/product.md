---
id: acelents
name: Acelents Website
status: active
owner: team-acelents
repo: https://github.com/dayalima/tep-web
default_url: https://dev.acelents.com
default_port: 443
health_check: https://dev.acelents.com/
tags: [astro, react, marketing-site, static]
last_reviewed: 2026-06-29
---

# Acelents Website

## Overview

The public marketing + product website for **Acelents**. It is a static site
(Astro 5 + React 19, `output: static`) whose job is to explain the product,
host the product tour, capture demo requests, and publish the blog. The live
dev deploy is at `https://dev.acelents.com`.

The same source is also ingested into this agent's knowledge base as raw code
chunks (see `apps/backend/src/agent/indexing.py` → `discover_tep_web_source`), so
the agent can answer code-level questions about routes, components, and the
tech stack — in addition to the prose here.

## How to run

### Prerequisites

- Node 22+
- pnpm
- Git

### Commands

```bash
git clone https://github.com/dayalima/tep-web
cd tep-web/apps
pnpm install
pnpm dev
```

`pnpm dev` runs `env-cmd -e local -- astro dev`, which serves the site at the
Astro default port.

### Verify

```bash
curl -I http://localhost:4321/
# HTTP/1.1 200 OK
```

Smoke-check the live deploy instead of local with:

```bash
curl -I https://dev.acelents.com/
```

## Features

Quick index. Detail lives in `features/<feature-id>.md`.

| Feature | Access path | Detail |
|---|---|---|
| Home | `/` | [features/home.md](features/home.md) |
| Product Tour | `/tour` | [features/tour.md](features/tour.md) |
| Plan a Demo | `/plan-a-demo` | [features/plan-a-demo.md](features/plan-a-demo.md) |
| Blog | `/blog` | [features/blog.md](features/blog.md) |

## Environment

| Variable | Required | Example | Notes |
|---|---|---|---|
| `SITE_URL` | no | `https://dev.acelents.com` | Build-time site origin; drives the sitemap + canonical URLs. Falls back to the dev deploy. |
| `.env-cmdrc` | yes | (committed) | Selects per-environment build config (`local`, `development`, `staging`, `production`) for `pnpm build:<env>`. |

## Deployment

Static build (`pnpm build:dev` / `build:staging` / `build:prod`) outputs to
`apps/dist/`. The dev deploy at `https://dev.acelents.com` is regenerated from
the `development` build. No server runtime — the output is plain HTML/CSS/JS.

## Common issues

### Port 4321 already in use

Astro's default dev port is 4321 (the same port this agent's own frontend
uses, so they collide if both run at once). Run the site on another port:

```bash
pnpm dev --port 4322
```

## Architecture notes

- **Framework**: Astro 5 (`output: static`) with `@astrojs/react` for the
  interactive islands. Sitemap via `@astrojs/sitemap`; image optimization via
  `sharp`.
- **Atomic design**: React components live under `apps/src/components/` split
  into `atoms/`, `molecules/`, `organisms/`, and `pages/` (page-level
  sections). Astro pages under `apps/src/pages/` are thin wrappers that mount
  these.
- **Routes**: `index.astro` (home), `tour/`, `plan-a-demo/`, `blog/`
  (with `blog/[slug].astro` for individual posts).
- **Styling**: Tailwind CSS v4 via `@tailwindcss/postcss`, plus
  `@tailwindcss/typography` and `tw-animate-css`. Global styles in
  `apps/globals.css`.
- **Build matrix**: `dev` / `build:dev` / `build:staging` / `build:prod`
  scripts in `apps/package.json` select the environment through `env-cmd`.
