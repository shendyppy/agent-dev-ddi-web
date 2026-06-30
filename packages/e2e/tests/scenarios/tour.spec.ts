import { test } from '@playwright/test';
import { join } from 'node:path';
import { ACELENTS_BASE_URL, screenshotDir } from '../helpers';

// The test title MUST equal the scenario name the agent passes to
// capture_screenshot(scenario=...) — `just screenshot <scenario>` greps it.
test('tour', async ({ page }) => {
  await page.goto(`${ACELENTS_BASE_URL}/tour`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: join(screenshotDir(), 'tour.png'), fullPage: true });
});
