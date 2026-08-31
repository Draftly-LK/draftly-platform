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
  },
});
