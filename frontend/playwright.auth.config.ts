import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Signed-out specs: they assert the real Clerk gate, so they need Clerk keys in
// frontend/.env and AUTH_BYPASS off. Own port and a fresh server, so a
// bypassed dev server left running on 4310 is never reused by mistake.
export default defineConfig({
  ...base,
  testIgnore: undefined,
  testMatch: ["auth-flow.spec.ts"],
  // The base config's auth project pins port 4310, so the dedicated suite
  // needs a project that targets the fresh server below.
  projects: [{ name: "auth", use: { baseURL: "http://127.0.0.1:4311" } }],
  webServer: {
    command: "pnpm dev -p 4311",
    url: "http://127.0.0.1:4311",
    env: { AUTH_BYPASS: "false" },
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
