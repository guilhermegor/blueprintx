import { defineConfig, devices } from '@playwright/test';

/**
 * E2E config for projects scaffolded from blueprintx ts-common.
 * Uses webServer to auto-start the dev server before tests.
 * Scoped to chromium-headless-shell to keep CI binaries minimal.
 *
 * After scaffolding, run `npx playwright install chromium` once to
 * download the browser binary (~150 MB; cached at ~/.cache/ms-playwright).
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },

  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.002 },
  },
});
