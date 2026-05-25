---
id: _template
name: Template Product
status: active
owner: team-name
repo: https://github.com/org/repo
default_url: http://localhost:3000
default_port: 3000
health_check: http://localhost:3000/api/health
tags: []
last_reviewed: 2026-05-25
---

# Template Product

> **How to use this template:**
> 1. Copy this folder: `cp -r docs/products/_template docs/products/<your-product-id>`
> 2. Rename — the folder name **must** equal the `id` frontmatter field.
> 3. Fill in every section. Don't delete sections; write "Not applicable" if one truly doesn't apply.
> 4. Delete this blockquote.
> 5. Update `docs/product-catalog.md` to list your product.
> 6. Run `just index`.

## Overview

What this product does in 2-3 short paragraphs. Who uses it. Why it exists.

The first paragraph is what the LLM sees most often during retrieval — make it self-contained and mention the product name explicitly.

## How to run

### Prerequisites

- List required tools with versions
- e.g., Node 22+, Python 3.11+, Docker

### Commands

```bash
git clone https://github.com/org/repo
cd repo
pnpm install
pnpm dev
```

### Verify

How to confirm it's running.

- Open http://localhost:3000
- Or check: `curl http://localhost:3000/api/health` returns `{"status":"ok"}`

## Features

| Feature | Access path | Detail |
|---|---|---|
| Example feature | `/example` | [features/example-feature.md](features/example-feature.md) |

## Environment

| Variable | Required | Example | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgres://localhost/db` | |
| `API_KEY` | no | `sk_...` | Only needed for X |

## Deployment

Where it runs in production, how to deploy. One paragraph + commands.

## Common issues

### Port already in use

Run `kill $(lsof -t -i:3000)` or change the `PORT` env var.

## Architecture notes

Anything non-obvious a developer should know. Cross-service deps, design decisions, gotchas. Skip if nothing notable.
