/**
 * Shared helpers for the screenshot-capture suite.
 *
 * Each scenario test navigates the live Acelents site and writes a full-page
 * PNG into the backend's screenshot dir, which FastAPI serves at /screenshots.
 * The capture_screenshot MCP skill then hands the URL to the agent, which
 * embeds it as a markdown image (see ADR 0008).
 */
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

/** Base URL of the site we capture from. Public dev deploy by default. */
export const ACELENTS_BASE_URL = process.env.ACELENTS_BASE_URL ?? 'https://dev.acelents.com';

/**
 * Where Playwright writes PNGs. Mirrors `settings.screenshot_dir`
 * (default <repo>/.data/screenshots) so the backend mount serves exactly what
 * we write. Override with SCREENSHOT_DIR; otherwise resolved relative to the
 * e2e package dir (recipes always `cd packages/e2e` first).
 *
 * Ensures the dir + the `_ondemand/` subdir exist so on-demand captures don't
 * fail on a fresh checkout.
 */
export function screenshotDir(): string {
  const dir =
    process.env.SCREENSHOT_DIR ?? join(process.cwd(), '..', '..', '.data', 'screenshots');
  mkdirSync(dir, { recursive: true });
  mkdirSync(join(dir, '_ondemand'), { recursive: true });
  return dir;
}
