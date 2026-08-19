# Product documentation format

This file is the **spec** for how we document each product the agent can answer about. Every product folder under [`docs/products/`](products/) must follow this format — both for human readability and so the RAG pipeline can chunk and retrieve reliably.

> **TL;DR for adding a new product:**
> 1. Copy [`docs/products/_template/`](products/_template/) to `docs/products/<product-id>/`.
> 2. Fill in `product.md` frontmatter + sections. Use exact section names from this spec.
> 3. Add one `features/<feature-id>.md` per significant feature.
> 4. Add a brief entry to [`docs/product-catalog.md`](product-catalog.md) (the index).
> 5. Run `just index` to rebuild ChromaDB.
> 6. Verify: ask the chatbot a question — it should return citations to your new files.

---

## Folder layout per product

```
docs/products/<product-id>/
├── product.md              ← required — overview, run, env, feature list
├── features/               ← required folder (can be empty for tiny products)
│   ├── <feature-id>.md     ← one file per non-trivial feature
│   └── ...
├── runbook.md              ← optional — operational troubleshooting
└── screenshots/            ← optional — curated PNGs (not auto-captured ones)
```

**Why split features into separate files?**
RAG chunks files at semantic boundaries. One feature per file = one retrievable unit. When a user asks "how do I access feature Y", the retriever pulls the exact file. Inline-everything in `product.md` causes retrieval collisions where Feature A's chunk overlaps with Feature B's chunk.

Rule of thumb: if a feature needs more than ~5 lines to explain, give it its own file.

---

## `product.md` — required structure

### Frontmatter (YAML, required)

```yaml
---
id: example-product              # kebab-case, must match folder name
name: Example Product             # display name
status: active                    # active | maintained | deprecated
owner: team-foo                   # team or @handle
repo: https://github.com/org/example
default_url: http://localhost:3000
default_port: 3000
health_check: http://localhost:3000/api/health
tags: [internal-tool, react, postgres]   # free-form, used for filtering
last_reviewed: 2026-05-25         # bump when you re-verify the doc is correct
---
```

**Required fields**: `id`, `name`, `status`, `owner`, `repo`, `default_url`, `default_port`, `last_reviewed`.
**Optional fields**: `health_check`, `tags`, anything else you want to attach.

The indexer reads frontmatter into metadata so the agent can filter by `status`, cite the `repo`, or check `health_check`.

### Body sections (in this exact order, with exact headings)

The agent's prompts assume these headings exist verbatim. Don't rename. If a section doesn't apply, write a single line "Not applicable" rather than removing the heading.

```markdown
# {{name}}

## Overview

2-3 short paragraphs. What this product does, who uses it, and why it exists.
Keep it punchy — this is what the LLM sees first when retrieval hits this file.

## How to run

### Prerequisites

- Bullet list of required tools/versions
- Use specific versions when relevant ("Node 22+", not "Node")

### Commands

```bash
# Verbatim, copy-pasteable commands.
# The chatbot will quote these back to users.
git clone https://github.com/org/example
cd example
pnpm install
pnpm dev
```

### Verify

How to confirm it's running. Default URL, a smoke check.

```bash
curl http://localhost:3000/api/health
# {"status":"ok"}
```

## Features

Quick index. Detail lives in `features/<feature-id>.md`.

| Feature | Access path | Detail |
|---|---|---|
| Login | `/login` | [features/login.md](features/login.md) |
| Dashboard | `/dashboard` (auth required) | [features/dashboard.md](features/dashboard.md) |

## Environment

| Variable | Required | Example | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgres://localhost/example` | |
| `STRIPE_KEY` | no | `sk_test_...` | Only for payment flows |

Mark secrets clearly. The chatbot will refuse to echo values, but documenting names is fine.

## Deployment

Where it lives in production, how to deploy. One paragraph + commands.

## Common issues

Recurring problems and how to resolve them. Each issue as a `### {short title}`.

### Port 3000 already in use

Run `kill $(lsof -t -i:3000)` or change `PORT` env var.

## Architecture notes

Optional. Anything a developer touching this product should know that isn't obvious from the code — design decisions, gotchas, cross-service dependencies.
```

---

## `features/<feature-id>.md` — required structure

One file per feature. The filename `<feature-id>` is kebab-case and stable (it's referenced by other docs).

### Frontmatter

```yaml
---
id: login                         # matches filename
name: Login                       # display name
product_id: example-product       # parent product id
requires_auth: false
access_path: /login               # primary URL/route
screenshot_scenarios:
  - example-login-flow            # Playwright test name (matches `--grep`)
---
```

### Body

```markdown
# Login

## What it does

1-2 sentences. The user's goal, not the implementation.

## How to access

Step-by-step navigation from a logged-out state:

1. Go to {{default_url}}/login
2. Enter email + password
3. Click "Sign in"

On success → redirected to /dashboard.

## Required permissions

Roles/scopes/feature-flags needed. "None" is a valid answer.

## Edge cases

- What happens with invalid credentials
- Password reset path
- 2FA flow (if applicable)

## Screenshot scenarios

- `example-login-flow` — captures the login page with empty form (`packages/e2e/tests/scenarios/example-login-flow.spec.ts`)

## Related features

- [Sign up](signup.md)
- [Password reset](password-reset.md)
```

---

## `runbook.md` — optional structure

Operational doc for when something is broken. Frontmatter not required.

```markdown
# {{product_name}} — Runbook

## Health checks

How to tell if it's broken from the outside.

## Common failure modes

### {{symptom}}

**Likely cause**: ...
**Fix**: ...
**Escalate to**: ...

## Logs & dashboards

Links to Grafana, Sentry, log aggregator, etc.

## Rollback procedure

Step-by-step.
```

---

## Chunking notes (for the RAG-curious)

The indexer uses recursive character splitting (800 tokens, 100 overlap). To get clean retrieval:

- **Headings create chunk boundaries.** Use them liberally. A 1500-line `product.md` with one heading is unrecoverable.
- **Repeat the product name in section bodies** when the section could stand alone (e.g., "To run **Example Product** locally, ..." not "To run it, ..."). Chunks lose their parent heading sometimes.
- **Avoid long tables.** If a table is > 20 rows, split it into multiple sections.
- **One feature per file** — see folder layout note above.

---

## Validation

`just validate-docs` exists and checks the **flat `docs/knowledge-base/` corpus** — the shape the web form writes (see [ADR 0011](adr/0011-knowledge-base-write-path.md)). The same function runs on every submission, so an invalid document is refused with a 422 before it reaches disk:

- [x] Frontmatter parses as YAML
- [x] `product_id`, `product_name`, `status` present and non-empty
- [x] `product_id` is kebab-case
- [x] `status` is one of `active` / `maintained` / `deprecated`
- [x] `last_reviewed` is an ISO date when present
- [x] Body is non-empty and has at least one markdown heading

Still TODO, and specific to the **per-product folders** this document specifies:

- [ ] Folder name matches frontmatter `id`
- [ ] All required `product.md` headings present in order
- [ ] `last_reviewed` is within 6 months
- [ ] Every feature listed in `product.md` has a corresponding `features/<id>.md`
- [ ] Every `screenshot_scenarios` entry has a matching Playwright test

For those, treat this spec as a code-review checklist.

---

## See also

- [`product-catalog.md`](product-catalog.md) — the index of all products (manually maintained)
- [`adr/0006-product-doc-format.md`](adr/0006-product-doc-format.md) — why this format
- [`products/_template/`](products/_template/) — copy-paste-able starting point
- [`products/example-product/`](products/example-product/) — a worked example (when present)
