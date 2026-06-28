---
name: frontend-design
description: Use when designing, refining, or reviewing UI in apps/frontend (Astro 6 + Preact islands). Covers layout, component composition, design tokens, responsiveness, and a11y. Invoke when the user asks to "improve the chat UI", "add a new panel", "make X look better", "audit accessibility", or pastes a Figma/screenshot/mockup.
---

# frontend-design

You are helping design and refine the chat-app frontend in `apps/frontend/` (Astro + Preact islands, no React/Next/heavy SPA per [`AGENTS.md`](../../../AGENTS.md)).

## Stack constraints (do not violate)

- **Astro 6** SSR pages in `src/pages/`. Interactive UI lives in **Preact islands** under `src/components/` and is hydrated via `client:*` directives.
- **No global state libraries** (Redux/Zustand/Jotai). Prefer Preact's `useState`/`useReducer` and Preact Signals when local state is insufficient.
- **No CSS-in-JS runtime**. Use plain CSS / CSS Modules / `<style>` blocks in Astro components.
- Markdown rendering in chat uses `marked` + `dompurify` (already wired in `Chat.tsx`).

## What to do when invoked

1. **Read first**: open the components you're touching and `apps/frontend/AGENTS.md` (if present). Look at existing patterns before proposing new ones.
2. **Match the design tokens** in `apps/frontend/src/styles/tokens.css` (create the file with this skill if absent — colors, spacing scale, type ramp, radii, motion durations).
3. **Output a design rationale** before code: layout sketch (ASCII or numbered description), why these tokens, what states are covered (idle/loading/error/empty), responsive behaviour at the 3 standard breakpoints (`<640`, `640–1024`, `>1024`), and a11y notes (focus order, ARIA, contrast).
4. **Then implement**. Keep components small and single-purpose. Hydration directive should be the most specific that works (`client:visible` > `client:idle` > `client:load`).
5. **Verify visually**: start `just dev` and screenshot the change. UI claims need eyeballs, not just type-checks.

## Design tokens (canonical reference)

If `tokens.css` is missing, scaffold with:

```css
:root {
  /* color */
  --color-bg: #0b0d12;
  --color-surface: #14171f;
  --color-surface-hover: #1c2030;
  --color-border: #262b3a;
  --color-text: #e6e8ef;
  --color-text-muted: #8b91a3;
  --color-accent: #6366f1;
  --color-accent-hover: #818cf8;
  --color-danger: #f87171;

  /* spacing — 4px base */
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem;
  --space-4: 1rem;    --space-6: 1.5rem; --space-8: 2rem;

  /* type */
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "JetBrains Mono", "Cascadia Code", Consolas, monospace;
  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-base: 1rem;
  --text-lg: 1.125rem; --text-xl: 1.25rem; --text-2xl: 1.5rem;

  /* radius / motion */
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-full: 999px;
  --motion-fast: 120ms; --motion-base: 200ms; --motion-slow: 320ms;
  --ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
}
```

Always reference tokens; never inline raw hex/px in a component.

## Accessibility checklist (apply before declaring done)

- Every interactive element is keyboard-reachable and shows a visible `:focus-visible` outline.
- Color contrast ≥ 4.5:1 for text, ≥ 3:1 for large text and UI components.
- `aria-live="polite"` on the chat transcript region so screen readers announce streamed tokens.
- Form inputs have associated `<label>` (visible or `sr-only`).
- Reduced motion: wrap non-essential transitions in `@media (prefers-reduced-motion: no-preference)`.

## Common asks → how to answer

| Ask | Approach |
|---|---|
| "Make the chat look better" | Audit current `Chat.tsx`, identify 3 highest-impact tweaks (spacing rhythm, message grouping, input affordance), propose tokens-only diff. |
| "Add a sidebar with conversation list" | Astro layout split with Preact island only for the active-conversation indicator. Keep list SSR-rendered. |
| "Loading / streaming indicator" | Use animated 3-dot or shimmer on the assistant bubble; respect `prefers-reduced-motion`. |
| "Dark / light theme" | Toggle a `data-theme` attribute on `<html>`; mirror token set under `[data-theme="light"]`. No JS framework needed. |

## Do not

- Pull in Tailwind, MUI, Chakra, shadcn, or any component library. The stack stays minimal by design.
- Convert an Astro page to a Preact SPA. Pages are SSR; islands are leaves.
- Hardcode colors or spacing. Add a token first.
- Ship UI changes without running `just dev` and visually confirming.
