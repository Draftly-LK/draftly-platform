import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // The `@/…` alias from tsconfig. Without it a module under test can only be
  // imported relatively, which quietly makes most of `lib/api` untestable —
  // type-only `@/` imports are erased, so the gap does not show until a test
  // touches a module that imports a runtime value that way.
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    // On in CI so `pnpm check` reports the number without a second test run;
    // locally, `pnpm test:coverage`. No thresholds yet: the plan ratchets from
    // a recorded baseline (docs/TESTING_PLAN.md §11.3).
    coverage: {
      enabled: process.env.CI === "true",
      provider: "v8",
      reporter: ["text-summary", "lcov"],
      all: true,
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.d.ts", "src/test/**"],
    },
  },
});
