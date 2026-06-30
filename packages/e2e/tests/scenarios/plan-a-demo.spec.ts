import { test } from '@playwright/test';
import { join } from 'node:path';
import { ACELENTS_BASE_URL, screenshotDir } from '../helpers';

// The test title MUST equal the scenario name the agent passes to
// capture_screenshot(scenario=...) — `just screenshot <scenario>` greps it.
test('plan-a-demo', async ({ page }) => {
  await page.goto(`${ACELENTS_BASE_URL}/plan-a-demo`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: join(screenshotDir(), 'plan-a-demo.png'), fullPage: true });
});
