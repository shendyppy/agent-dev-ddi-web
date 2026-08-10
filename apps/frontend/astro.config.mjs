// @ts-check
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'astro/config';
import preact from '@astrojs/preact';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  // compat: true aliases react/react-dom → preact/compat at the Vite level,
  // which is what lets Radix UI primitives (used by our shadcn-style ui/
  // components) run on Preact without pulling in React itself.
  integrations: [preact({ compat: true })],
  server: {
    port: Number(process.env.FRONTEND_PORT ?? 4321),
  },
  // Tailwind v4 is config-file-free — all tokens live in global.css @theme.
  // The vite plugin picks up any CSS file that contains `@import "tailwindcss"`.
  vite: {
    plugins: [tailwindcss()],
    // Read .env from the REPO ROOT, not apps/frontend.
    //
    // Vite defaults envDir to the project root, which here is apps/frontend —
    // where no .env exists. The result was a hydration failure that gave no
    // hint of its cause: `supabaseUrl is required`, thrown inside
    // lib/supabase.ts at module load, which killed the whole Chat island and
    // rendered a blank page.
    //
    // Pointing at the monorepo root means one .env for both apps, and the
    // Supabase credentials never have to be duplicated into a second file that
    // could drift or be committed by accident. Only PUBLIC_* keys are exposed
    // to the browser bundle — the rest of the file stays server-side, so
    // widening the directory does not widen what ships.
    envDir: fileURLToPath(new URL('../../', import.meta.url)),
  },
});
