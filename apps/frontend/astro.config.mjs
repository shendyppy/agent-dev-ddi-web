// @ts-check
import { defineConfig } from 'astro/config';
import preact from '@astrojs/preact';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  integrations: [preact()],
  server: {
    port: Number(process.env.FRONTEND_PORT ?? 4321),
  },
});
