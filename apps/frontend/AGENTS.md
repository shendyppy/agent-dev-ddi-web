# apps/frontend — AGENTS.md

Conventions for editing the Astro frontend. Read repo-root [`AGENTS.md`](../../AGENTS.md) first.

## What this is

- **Astro** for static pages (product catalog browse, deep links, landing).
- **Preact island** for the chat widget — isolated client-side state, kept small.
- **Tailwind** for styling (TBD — pick before first UI work if a theme is needed).
- Talks to the backend at `http://localhost:8000` via SSE on `/api/chat`.

## Rules

1. **Static by default.** New pages should be `.astro` and ship zero JS unless interactivity is required.
2. **One island per interactive widget.** Don't pull React/Vue/Svelte — Preact is intentional.
3. **No SSR-with-server-runtime**. We deploy to Cloudflare Pages — keep output `static`. If you must SSR, use edge functions and document why in an ADR.
4. **API base URL** comes from `import.meta.env.PUBLIC_API_BASE_URL`. Never hardcode `localhost:8000` in components.
5. **No state management library.** `useState` / `useReducer` is enough for the chat widget. If complexity grows, prefer URL state or backend session state over a global store.

## Layout

```
src/
├── components/        ← Astro components (.astro) and Preact islands (.tsx)
│   └── Chat.tsx       ← the chat widget (Preact island)
├── layouts/
├── pages/             ← Astro routes
└── assets/
```

## Local dev

```powershell
just dev-fe            # astro dev, port 4321
just test-fe           # vitest (when wired)
just build-fe          # production build → dist/
```
