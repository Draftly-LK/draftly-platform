import { defineConfig } from "@playwright/test";

const ci = Boolean(process.env.CI);

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
  // Retries absorb CI infrastructure noise only. A spec that passes only on a
  // retry is a flake to fix (TESTING_PLAN.md §11.5), not a pass.
  retries: ci ? 2 : 0,
  // CI keeps an HTML report and JUnit XML as artifacts; locally, one line.
  reporter: ci
    ? [
        ["github"],
        ["html", { open: "never" }],
        ["junit", { outputFile: "test-results/junit.xml" }],
      ]
    : "line",
  webServer: {
    command: "pnpm dev -p 4310",
    url: "http://127.0.0.1:4310",
    // Next does not override variables already set, so these win over .env.
    // The Sinhala specs need the locale toggle even where .env turns it off.
    env: { AUTH_BYPASS: "true", MULTILINGUAL_LANGUAGE_SUPPORT: "true" },
    reuseExistingServer: !ci,
    timeout: 120_000,
  },
});
