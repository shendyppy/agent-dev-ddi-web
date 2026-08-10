import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

// jsdom, not node: `lib/chat.ts` registers a DOMPurify hook at module load, so
// importing anything from it needs a DOM to exist first. That hook is a
// security control (forces rel="noopener" on every LLM-emitted link), so
// running tests without a DOM would mean testing a different module than the
// one that ships.
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
