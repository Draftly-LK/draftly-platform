import type * as ClerkServer from "@clerk/nextjs/server";
import { NextRequest, type NextFetchEvent } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Clerk is the external boundary, so only its middleware wrapper is replaced:
// the stand-in runs our handler with an `auth` whose `protect` is recorded.
// createRouteMatcher stays real — the public-route list is ours to test.
const protect = vi.fn();
const clerkRan = vi.fn();

vi.mock("@clerk/nextjs/server", async (importOriginal) => {
  const actual = await importOriginal<typeof ClerkServer>();
  const { NextResponse } = await import("next/server");
  return {
    ...actual,
    clerkMiddleware:
      (
        handler: (
          auth: { protect: () => Promise<void> },
          request: NextRequest,
        ) => Promise<void>,
      ) =>
      async (request: NextRequest) => {
        clerkRan();
        await handler({ protect: async () => protect() }, request);
        return NextResponse.next();
      },
  };
});

const { default: middleware, config } = await import("./middleware");

const event = {} as NextFetchEvent;

function request(path: string): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:4310"));
}

function redirectPath(response: unknown): string | null {
  const location =
    response instanceof Response ? response.headers.get("location") : null;
  return location ? new URL(location).pathname : null;
}

function passedThrough(response: unknown): boolean {
  return (
    response instanceof Response &&
    response.headers.get("x-middleware-next") === "1"
  );
}

function configureClerk(): void {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_synthetic");
  vi.stubEnv("CLERK_SECRET_KEY", "sk_test_synthetic");
}

function unconfigureClerk(): void {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "");
  vi.stubEnv("CLERK_SECRET_KEY", "");
}

describe("middleware gate order: bypass → fail closed → public route → protect", () => {
  beforeEach(() => {
    protect.mockClear();
    clerkRan.mockClear();
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("AUTH_BYPASS", "false");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("lets every request through under the dev bypass, before the fail-closed check", async () => {
    vi.stubEnv("AUTH_BYPASS", "true");
    unconfigureClerk();

    const response = await middleware(request("/matters"), event);

    expect(passedThrough(response)).toBe(true);
    expect(clerkRan).not.toHaveBeenCalled();
  });

  it("ignores the bypass in production and fails closed", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("AUTH_BYPASS", "true");
    unconfigureClerk();
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    const response = await middleware(request("/matters"), event);

    expect(redirectPath(response)).toBe("/clerk-not-configured");
  });

  it("redirects every page to the not-configured screen while Clerk is unconfigured", async () => {
    unconfigureClerk();

    const response = await middleware(
      request("/matters/matter-rta-001"),
      event,
    );

    expect(redirectPath(response)).toBe("/clerk-not-configured");
    expect(clerkRan).not.toHaveBeenCalled();
  });

  it("keeps the not-configured screen reachable, so the redirect cannot loop", async () => {
    unconfigureClerk();

    const response = await middleware(request("/clerk-not-configured"), event);

    expect(passedThrough(response)).toBe(true);
  });

  it.each([
    "/sign-in",
    "/sign-in/factor-one",
    "/sign-up",
    "/clerk-not-configured",
    "/animations/gavel-ascii.json",
  ])("does not demand a session on the public route %s", async (path) => {
    configureClerk();

    await middleware(request(path), event);

    expect(clerkRan).toHaveBeenCalledOnce();
    expect(protect).not.toHaveBeenCalled();
  });

  it.each(["/", "/matters", "/profile", "/onboarding", "/api/v1/me"])(
    "demands a session on %s",
    async (path) => {
      configureClerk();

      await middleware(request(path), event);

      expect(protect).toHaveBeenCalledOnce();
    },
  );
});

describe("middleware matcher", () => {
  // Next treats each entry as a full-path pattern; anchoring gives the same test.
  const matchers = config.matcher.map((pattern) => new RegExp(`^${pattern}$`));
  const runsOn = (path: string) =>
    matchers.some((matcher) => matcher.test(path));

  it.each([
    "/",
    "/matters/matter-rta-001",
    "/sign-in",
    "/api/v1/me",
    "/exports/manifest.json",
    "/animations/gavel-ascii.json",
  ])("runs on %s", (path) => {
    expect(runsOn(path)).toBe(true);
  });

  it.each([
    "/_next/static/chunks/main.js",
    "/images/logo-mark-blue.png",
    "/favicon.ico",
    "/fonts/plex.woff2",
    "/styles/app.css",
  ])("skips the static asset %s", (path) => {
    expect(runsOn(path)).toBe(false);
  });
});
