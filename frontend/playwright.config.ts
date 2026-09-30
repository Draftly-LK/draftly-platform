import { defineConfig } from "@playwright/test";

/**
 * Two dev servers, because the suite needs two incompatible environments and
 * both are decided by process env at server start:
 *
 * - `auth` (port 4310): authentication ENFORCED. `auth-flow.spec.ts` asserts
 *   that signed-out visitors are bounced to /sign-in, so AUTH_BYPASS is forced
 *   off here even if a developer's `.env` turns it on. Clerk keys come from
 *   `.env` as usual.
 * - `workspace` (port 4311): the deterministic offline demo. AUTH_BYPASS is on
 *   and the API base URL and Clerk keys are blanked, so every screen renders
 *   from the seeded `lib/data.ts` mocks with no backend, no Clerk script, and
 *   no dependence on what a developer happens to have in `.env`. (Next never
 *   overrides a variable that is already defined in process env, and the app
 *   treats an empty value as "not configured".)
 *
 * The second server builds into its own distDir so the two `next dev`
 * processes do not fight over `.next`.
 */
const AUTH_PORT = 4310;
const WORKSPACE_PORT = 4311;
const authURL = `http://127.0.0.1:${AUTH_PORT}`;
const workspaceURL = `http://127.0.0.1:${WORKSPACE_PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    trace: "retain-on-failure",
    channel: "chromium",
  },
  reporter: "line",
  projects: [
    {
      name: "auth",
      testMatch: /auth-flow\.spec\.ts$/,
      use: { baseURL: authURL },
    },
    {
      name: "workspace",
      testIgnore: /auth-flow\.spec\.ts$/,
      use: { baseURL: workspaceURL },
    },
  ],
  webServer: [
    {
      command: `pnpm dev -p ${AUTH_PORT}`,
      url: `${authURL}/sign-in`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { AUTH_BYPASS: "false" },
    },
    {
      command: `pnpm dev -p ${WORKSPACE_PORT}`,
      url: workspaceURL,
      // Never reused: a stray server on this port could be in the wrong mode,
      // and the specs are only meaningful against the mock-data environment.
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        AUTH_BYPASS: "true",
        NEXT_PUBLIC_API_BASE_URL: "",
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "",
        CLERK_SECRET_KEY: "",
        NEXT_DIST_DIR: ".next-e2e",
      },
    },
  ],
});
