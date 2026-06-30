import { test } from '@playwright/test';
import { join } from 'node:path';
import { ACELENTS_BASE_URL, screenshotDir } from '../helpers';

/**
 * On-demand capture. The capture_screenshot handler passes a URL via
 * CAPTURE_URL and an output path via CAPTURE_OUT, then runs
 * `just screenshot-url <url> <slug>` which greps this test.
 *
 * CAPTURE_URL may be a path ("/tour") or a full URL ("https://..."); we resolve
 * it against ACELENTS_BASE_URL when it is relative. Skipped when CAPTURE_URL is
 * unset so a bare `playwright test` run does not fire a live capture.
 */
test('capture-url', async ({ page }) => {
  const raw = process.env.CAPTURE_URL;
  test.skip(!raw, 'CAPTURE_URL must be set (on-demand only)');

  const target = raw!.startsWith('http') ? raw! : `${ACELENTS_BASE_URL}${raw!}`;
  const out = process.env.CAPTURE_OUT ?? join(screenshotDir(), '_ondemand', 'capture.png');

  await page.goto(target, { waitUntil: 'networkidle' });
  await page.screenshot({ path: out, fullPage: true });
});
