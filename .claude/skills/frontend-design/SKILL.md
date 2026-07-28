---
name: frontend-design
description: Use when designing, refining, or reviewing UI in apps/frontend (Astro 6 + Preact islands + Tailwind v4 + shadcn-style components). Covers layout, component composition, design tokens, responsiveness, and a11y. Invoke when the user asks to "improve the chat UI", "add a new panel", "make X look better", "audit accessibility", or pastes a Figma/screenshot/mockup.
---

# frontend-design

You are helping design and refine the chat-app frontend in `apps/frontend/` (Astro + Preact islands per [`AGENTS.md`](../../../AGENTS.md)).

## Stack constraints (do not violate)

- **Astro 6**, `output: 'static'` — pages in `src/pages/` are prerendered, no server runtime (we deploy to Cloudflare Pages). Interactive UI lives in **Preact islands** under `src/components/` and hydrates via `client:*`.
- **Tailwind v4** is the styling system, wired as a Vite plugin (`@tailwindcss/vite`) in `astro.config.mjs`. It is **config-file-free** — there is no `tailwind.config.js` and you should not add one. All tokens live in the `@theme` block of `src/styles/global.css`.
- **shadcn/ui-style components** in `src/components/ui/` (button, textarea, avatar, toggle-group), built on **Radix primitives** running under `preact/compat` (enabled by `preact({ compat: true })`). Add new atoms in this style; don't introduce MUI, Chakra, Mantine, or a second component library.
- **No global state libraries** (Redux/Zustand/Jotai). `useState`/`useReducer` is enough; chat state lives in `src/hooks/use-chat.ts`.
- **No CSS-in-JS runtime.** Utilities first; scoped `<style>` blocks in `.astro` files for things utilities can't reach (see `src/pages/index.astro`'s skeleton).
- Markdown rendering uses `marked` + `dompurify`, wrapped by `renderMarkdown()` in `src/lib/chat.ts`.

## Design tokens — the single source of truth

Tokens live in **`apps/frontend/src/styles/global.css`** inside `@theme`. There is **no `tokens.css` — do not create one.** Each `--color-*` in `@theme` automatically generates `bg-*`, `text-*`, `border-*`, `ring-*` utilities.

The vocabulary is **shadcn's**, so ported `ui/` components style themselves correctly. Values are the Odyssey brand palette (near-black ink, deep-maroon primary, warm gold accent, cool-light surfaces).

Available color tokens:

```
background  foreground        card    card-foreground     popover  popover-foreground
primary     primary-foreground  primary-soft
secondary   secondary-foreground
muted       muted-foreground
accent      accent-foreground   ← shadcn "accent" = subtle hover bg, NOT the brand color
destructive destructive-foreground   success   warning
border      input    ring
gold        ← decorative only; fails AA as small text
```

Plus `--font-sans` / `--font-mono` and `--radius-xs|sm|md|lg|full`.

### The #1 bug in this codebase: inventing token names

A Tailwind class naming a token that isn't in `@theme` **compiles to nothing and fails silently** — no error, no warning, just an unstyled element. Legacy names from an older iteration (`bg-surface`, `text-ink`, `bg-surface-hover`, `text-text-muted`, `border-accent-hover`, `text-danger`) **do not exist here.**

Real example still in the tree — `src/components/chat/CitationList.tsx:40` uses `bg-surface`, which renders as transparent:

```tsx
class="… border border-border bg-surface px-2.5 py-1 …"   // ✗ bg-surface is not a token
class="… border border-border bg-card px-2.5 py-1 …"      // ✓
```

Before shipping any class you haven't used before, grep `global.css` for the token name. When auditing UI that "looks broken for no reason", check for phantom tokens first.

**Corollary — don't name a class literally in a comment.** The v4 scanner reads raw file text with no syntax awareness, so writing ``// was `bg-red-500`, now uses the token`` emits `bg-red-500` into the bundle as dead CSS. Describe the class in prose instead ("a hardcoded palette red"). Verify with a build: `pnpm build`, then grep `dist/_astro/*.css` for the class you expect to be gone.

### Rules

- Colors: **always** a token utility (`bg-card`, `text-muted-foreground`, `border-border`). Never a raw hex, never `bg-gray-800`, never `bg-red-500` — that last one is currently hardcoded on the mic button in `ChatComposer.tsx` and should be `bg-destructive`.
- Spacing/size: Tailwind's scale (`gap-2.5`, `px-6`). Arbitrary values (`text-[0.9375rem]`, `max-w-[760px]`) are accepted in this codebase for type ramp and measure — keep them rare and consistent with neighbours.
- Radii: `rounded-sm|md|lg|2xl|full` map to the `--radius-*` tokens.
- Need a genuinely new color? Add it to `@theme` **and** its dark-mode counterpart, then use it.

### Dark mode

Dark mode is a **`@media (prefers-color-scheme: dark)` block that reassigns the same custom properties** — every utility flips automatically. Consequences:

- **Never write `dark:` variants in markup.** They are unnecessary and will drift.
- Any new token must be defined in **both** blocks or it will be invisible in one theme.
- There is no `data-theme` attribute and no theme toggle. If the user asks for a manual toggle, that's a real change: mirror the token set under `:root[data-theme="…"]`, keep the media query as the default, and say so.

## What to do when invoked

1. **Read first**: the components you're touching, `apps/frontend/AGENTS.md`, and the `@theme` block of `global.css`. Match existing patterns before inventing new ones.
2. **Output a design rationale before code**: layout sketch (ASCII or numbered), which tokens and why, states covered (idle / loading / streaming / error / empty), responsive behaviour at the three breakpoints, a11y notes (focus order, ARIA, contrast).
3. **Then implement.** Small, single-purpose components. Follow the existing atomic split: atoms in `ui/`, molecules/organisms in `components/chat/`, and keep `Chat.tsx` a thin shell that only wires `useChat()` into regions.
4. **Verify visually**: `just dev-fe` (port 4321) and screenshot. UI claims need eyeballs, not just type-checks.

### Hydration directives

Prefer the most specific directive that works — **except** where a module has browser-only top-level side effects. `Chat.tsx` is `client:only="preact"` on purpose: DOMPurify is a factory under Node SSR and breaks the build otherwise. `client:only` components render nothing on the server, so give them a slot placeholder that mirrors the real shell to avoid layout shift (see the `chat-skeleton` in `index.astro`).

## Responsive behaviour

Mobile-first: unprefixed classes target `<640px`, then layer `sm:` (≥640), `md:` (≥768), `lg:` (≥1024). Design for the three standard bands: `<640` / `640–1024` / `>1024`.

Recurring problems in this UI, worth checking every time:

- **The header** (`ChatHeader.tsx`) packs title + scope picker + model chip + language toggle into one row. Below ~640px this overflows. Drop the model chip, let the scope picker shrink, or wrap to a second row — don't just let it squash.
- **`h-screen`** on the chat shell breaks on mobile browsers whose URL bar resizes the viewport. Prefer `h-dvh` (with `h-screen` as the fallback declaration).
- **Fixed measures** like `max-w-[760px]` need a `w-full` sibling and horizontal padding that shrinks on small screens (`px-4 sm:px-6`).
- **Tap targets** ≥ 44×44px on touch. The 40px circular composer buttons are the floor — don't go smaller.
- **Overflowing content** (tables, `<pre>`, long URLs) must scroll inside its own container so the page never scrolls sideways. `global.css` already does this for `.markdown-body`; match it for anything new.

## Styling content you can't reach with utilities

Markdown is injected via `dangerouslySetInnerHTML`, so Tailwind's scanner never sees those nodes and Preflight has already stripped their default margins, heading sizes, and list markers. Rules for that content live in the `.markdown-body` block of `global.css` — extend it there, scoped, referencing `var(--color-*)` directly. Same applies to keyframe-driven classes (`.typing-dot`, `.anim-in`).

## Accessibility checklist (apply before declaring done)

- Every interactive element is keyboard-reachable with a visible `:focus-visible` ring (use `ring-ring`).
- Contrast ≥ 4.5:1 for body text, ≥ 3:1 for large text and UI boundaries. `gold` fails as small text — decorative only.
- `role="log"` + `aria-live="polite"` on the transcript so streamed tokens are announced.
- Inputs have an associated `<label>` (visible or `sr-only`).
- Icon-only buttons carry `aria-label`.
- Non-essential motion sits behind `@media (prefers-reduced-motion: no-preference)`, or uses Tailwind's `motion-safe:` variant.
- Loading skeletons are `aria-hidden` with a matching `sr-only` `role="status"` for assistive tech.

## Common asks → how to answer

| Ask | Approach |
|---|---|
| "Make the chat look better" | Audit for phantom tokens first, then pick the 3 highest-impact tweaks (spacing rhythm, message grouping, input affordance) and propose a tokens-only diff. |
| "Make it responsive" | Walk the three breakpoints against the recurring-problems list above; fix header overflow and `h-screen` before anything cosmetic. |
| "Make it more futuristic / on-brand" | Adjust the `@theme` values and the shared surfaces (elevation, border treatment, motion) rather than restyling components one by one. One change, whole-app effect. |
| "Add a sidebar with conversation list" | Astro layout split; Preact island only for the active-conversation indicator. Keep the list static-rendered. |
| "Loading / streaming indicator" | Extend the existing `.typing-dot` pattern; respect `prefers-reduced-motion`. |
| "Dark / light theme toggle" | Add `:root[data-theme="…"]` blocks mirroring the existing token set, keep the media query as default, persist the choice, and flag it as an architectural change. |
| "Add a new component" | Check `ui/` first; if it's a shadcn primitive, port it in that style on Radix + `cva` + `cn()` from `lib/utils.ts`. |

## Do not

- Add `tailwind.config.js`, a `tokens.css`, or a second styling system. Tokens go in `global.css` `@theme`.
- Use a Tailwind class whose token isn't defined in `@theme` — it fails silently.
- Write `dark:` variants. Dark mode flips via the media-query token block.
- Hardcode colors (`bg-red-500`, `#7a0e15`). Use tokens.
- Pull in React proper, MUI, Chakra, or a state-management library.
- Convert an Astro page into a Preact SPA. Pages are static; islands are leaves.
- Ship UI changes without running `just dev-fe` and looking at them.
