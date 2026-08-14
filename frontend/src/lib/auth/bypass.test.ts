import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isAuthBypassEnabled, warnIfBypassSetInProduction } from "./bypass";

describe("auth bypass helpers", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    // NODE_ENV is typed read-only, so it is set via stubEnv rather than by
    // assignment; unstubbing restores it alongside the plain-env reset.
    vi.unstubAllEnvs();
    process.env = originalEnv;
  });

  it("returns false in production even if AUTH_BYPASS=true", () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.AUTH_BYPASS = "true";
    expect(isAuthBypassEnabled()).toBe(false);
  });

  it("returns true in non-production when AUTH_BYPASS=true", () => {
    vi.stubEnv("NODE_ENV", "development");
    process.env.AUTH_BYPASS = "true";
    expect(isAuthBypassEnabled()).toBe(true);
  });

  it("logs an error if AUTH_BYPASS=true in production", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubEnv("NODE_ENV", "production");
    process.env.AUTH_BYPASS = "true";

    warnIfBypassSetInProduction();

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining("AUTH_BYPASS=true is set but NODE_ENV=production"),
    );
    consoleSpy.mockRestore();
  });
});
