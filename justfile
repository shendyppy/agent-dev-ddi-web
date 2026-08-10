# Documentation Agent Bot — task runner
# https://just.systems
#
# Run `just --list` to see all recipes. Tab-completion: see https://just.systems/man/en/chapter_56.html

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set dotenv-load := true

# Default: show recipes
_default:
    @just --list

# ─── Setup ────────────────────────────────────────────────────────────────────

# One-shot install: all deps across the monorepo
bootstrap: install-fe install-be install-e2e
    @echo ""
    @echo "Bootstrap complete. Copy .env.example to .env and fill in keys."
    @echo "Then: just dev"

install-fe:
    cd apps/frontend; pnpm install

install-be:
    cd apps/backend; uv sync

install-e2e:
    cd packages/e2e; pnpm install
    cd packages/e2e; pnpm exec playwright install --with-deps

# ─── Development ──────────────────────────────────────────────────────────────

# Start FE + BE concurrently (uses pnpm concurrently script under the hood)
dev:
    npx concurrently -n "be,fe" -c "blue,magenta" "just dev-be" "just dev-fe"

dev-fe:
    cd apps/frontend; pnpm dev

dev-be:
    cd apps/backend; uv run uvicorn agent.server:app --reload --port 8000 --app-dir src

# ─── RAG indexing ─────────────────────────────────────────────────────────────

# (Re)build the ChromaDB index from docs/
index:
    cd apps/backend; uv run python -m agent.indexing

# Drop the index and rebuild from scratch
reindex:
    Remove-Item -Recurse -Force .data/chroma -ErrorAction SilentlyContinue
    just index

# ─── Evals ────────────────────────────────────────────────────────────────────

# Run the full eval suite.
# Runs from the repo root — `evals/` lives here, not under apps/backend — with
# the backend's `src` on PYTHONPATH so `agent.*` imports resolve. `uv run
# --project` picks the backend venv without changing cwd.
eval *args:
    $env:PYTHONPATH="{{justfile_directory()}}/apps/backend/src"; uv run --project apps/backend python -m evals.run {{args}}

# Run evals in fast mode (cached LLM responses where possible)
eval-fast *args:
    just eval --fast {{args}}

# ─── MCP servers ──────────────────────────────────────────────────────────────

# List all configured MCP servers
mcp-list:
    cd apps/backend; uv run python -m agent.mcp_clients --list

# Inspect a single MCP server interactively (uses MCP Inspector)
mcp-inspect skill:
    npx -y @modelcontextprotocol/inspector uv --directory apps/backend run python -m mcp_servers.{{skill}}.server

# ─── E2E / Playwright ─────────────────────────────────────────────────────────

# Run all Playwright tests
test-e2e:
    cd packages/e2e; pnpm exec playwright test

# Trigger a specific screenshot scenario (used by the capture_screenshot skill).
# SCREENSHOT_DIR is forced to the backend's screenshot dir so the PNG lands
# where FastAPI serves /screenshots, regardless of cwd. PowerShell `$env:`
# syntax because justfile's windows-shell is powershell (bash-style VAR=x
# would not work) — see CLAUDE.md.
screenshot scenario:
    cd packages/e2e; $env:SCREENSHOT_DIR="{{justfile_directory()}}/.data/screenshots"; pnpm exec playwright test --grep "{{scenario}}"

# Capture an arbitrary live URL on the Acelents site on demand (used by the
# capture_screenshot skill's `url` path). <slug> becomes the cached filename.
# Mirrors `screenshot` but feeds CAPTURE_URL/CAPTURE_OUT to the on-demand test.
screenshot-url url slug:
    cd packages/e2e; $env:CAPTURE_URL="{{url}}"; $env:CAPTURE_OUT="{{justfile_directory()}}/.data/screenshots/_ondemand/{{slug}}.png"; $env:SCREENSHOT_DIR="{{justfile_directory()}}/.data/screenshots"; pnpm exec playwright test --grep "capture-url"

# ─── Quality ──────────────────────────────────────────────────────────────────

test: test-be test-evals test-fe test-e2e

test-be:
    cd apps/backend; uv run pytest

# Unit tests for the eval suite's own assertion logic. Separate from test-be
# because `evals/` lives at the repo root, outside the backend's testpaths —
# and a broken assertion is invisible (it looks exactly like a passing one),
# so it needs tests of its own.
test-evals:
    $env:PYTHONPATH="{{justfile_directory()}}/apps/backend/src;{{justfile_directory()}}"; uv run --project apps/backend python -m pytest evals -q

test-fe:
    cd apps/frontend; pnpm test

lint:
    cd apps/backend; uv run ruff check .
    cd apps/frontend; pnpm lint

fmt:
    cd apps/backend; uv run ruff format .
    cd apps/frontend; pnpm fmt

# Same checks as `fmt` but read-only — for CI, which must fail on drift
# rather than silently rewriting the checkout.
fmt-check:
    cd apps/backend; uv run ruff format --check .
    cd apps/frontend; pnpm fmt:check

# ─── Observability ────────────────────────────────────────────────────────────

# Pretty-print a Langfuse trace by session_id
trace session_id:
    cd apps/backend; uv run python -m agent.observability.fetch_trace {{session_id}}

# ─── Build / Deploy ───────────────────────────────────────────────────────────

build-fe:
    cd apps/frontend; pnpm build

build-be:
    cd apps/backend; uv build

# ─── Maintenance ──────────────────────────────────────────────────────────────

# Clean all caches and build artifacts
clean:
    Remove-Item -Recurse -Force apps/frontend/node_modules,apps/frontend/dist,apps/frontend/.astro -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force apps/backend/.venv,apps/backend/.uv-cache,apps/backend/.pytest_cache,apps/backend/.ruff_cache -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force packages/e2e/node_modules,packages/e2e/test-results,packages/e2e/playwright-report -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force .data,evals/.runs,evals/.cache -ErrorAction SilentlyContinue
