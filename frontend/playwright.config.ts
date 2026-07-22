import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: { baseURL: "http://127.0.0.1:4310", trace: "retain-on-failure" },
  reporter: "line",
});

