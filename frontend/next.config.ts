import createNextIntlPlugin from "next-intl/plugin";
import path from "node:path";

const withNextIntl = createNextIntlPlugin("./src/lib/i18n/request.ts");

export default withNextIntl({
  reactStrictMode: true,
  poweredByHeader: false,
  // Docker builds set NEXT_OUTPUT=standalone (see Dockerfile); `next start` and CI stay on the default output.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // The Playwright workspace server runs beside the normal dev server and needs
  // its own build directory (see playwright.config.ts). Unset everywhere else.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // The repo root, which the Docker image's /repo/frontend layout relies on.
  // Not on Vercel: `vercel deploy` from frontend/ uploads only this folder, so
  // the parent does not exist there and tracing looks for .next one level up.
  ...(process.env.VERCEL ? {} : { outputFileTracingRoot: path.join(process.cwd(), "..") }),
});
