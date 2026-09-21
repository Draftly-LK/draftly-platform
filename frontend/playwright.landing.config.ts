import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/landing-page',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  // The ASCII artwork has tens of thousands of spans. Full DOM traces make
  // each click expensive; save viewport screenshots and audit JSON instead.
  use: { baseURL: 'http://127.0.0.1:4175', channel: 'chromium', trace: 'off' },
  reporter: 'line',
  webServer: [
    { command: 'node ../landing-page/serve.mjs site-mirror 4175', url: 'http://127.0.0.1:4175', reuseExistingServer: !process.env.CI },
    { command: 'pnpm dev --port 4310', url: 'http://127.0.0.1:4310', reuseExistingServer: !process.env.CI, timeout: 120_000 },
  ],
});
