# Frontend — Astro + Preact island

Static-first Astro site. The chat widget is a single Preact island (`src/components/Chat.tsx`) loaded via `client:load` on the home page.

See [`AGENTS.md`](AGENTS.md) for editing conventions.

## Commands

```powershell
just dev-fe       # astro dev (port 4321)
just build-fe     # production build → dist/
```

Or directly from this folder: `pnpm dev` / `pnpm build`.

## Env

- `PUBLIC_API_BASE_URL` — backend URL (defaults to `http://localhost:8000` in dev).
- `FRONTEND_PORT` — dev server port (default `4321`).

Public env vars in Astro must be prefixed `PUBLIC_`.

## Deployment

Cloudflare Pages — see [`../../docs/adr/0005-deployment-strategy.md`](../../docs/adr/0005-deployment-strategy.md).
