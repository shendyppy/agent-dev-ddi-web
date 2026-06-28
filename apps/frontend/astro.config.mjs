// @ts-check
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
  vite: { plugins: [tailwindcss()] },
});
