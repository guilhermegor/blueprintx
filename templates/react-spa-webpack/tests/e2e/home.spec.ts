import { expect, test } from '@playwright/test';

/**
 * Sample e2e test against the scaffolded example capability.
 * Demonstrates two patterns:
 *   1. Behavior — assert the app boots and React reaches a render state.
 *   2. Visual regression — snapshot the page against a committed baseline.
 *
 * Run `npm run test:e2e:update` once after scaffolding to commit the
 * initial baseline. Subsequent `npm run test:e2e` runs assert against it.
 */
test('home page boots and reaches a render state', async ({ page }) => {
  await page.goto('/');
  // Example capability shows one of: Loading..., Error: ..., or the Notes heading.
  await expect(page.locator('body')).toContainText(/Notes|Loading|Error/);
});

test('home page matches the committed visual baseline', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toContainText(/Notes|Loading|Error/);
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveScreenshot('home.png', { fullPage: true });
});
