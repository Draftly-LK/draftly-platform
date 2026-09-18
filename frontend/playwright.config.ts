import { defineConfig } from "@playwright/test";

// App specs run signed in via AUTH_BYPASS on the dev server. The bypass is
// ignored under NODE_ENV=production, so this must stay a dev server. The
// signed-out Clerk specs run from playwright.auth.config.ts instead.
export default defineConfig({
  testDir: "./tests/e2e",
  testIgnore: ["auth-flow.spec.ts"],
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: "http://127.0.0.1:4310",
    trace: "retain-on-failure",
    channel: "chromium",
  },
  reporter: "line",
  webServer: {
    command: "pnpm dev -p 4310",
    url: "http://127.0.0.1:4310",
    // Next does not override variables already set, so this wins over .env.
    env: { AUTH_BYPASS: "true" },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
