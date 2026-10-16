import { expect, test } from '@playwright/test';

test('home page boots and reaches a render state', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toContainText(/Notes|Loading|Error/);
});

test('home page matches the committed visual baseline', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toContainText(/Notes|Loading|Error/);
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveScreenshot('home.png', { fullPage: true });
});
