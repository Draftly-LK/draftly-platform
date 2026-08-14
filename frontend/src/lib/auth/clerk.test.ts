import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasClerkPublishableKey, isClerkConfigured } from "./clerk";

describe("clerk configuration helpers", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("returns false for publishable key when env var is missing", () => {
    delete process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
    expect(hasClerkPublishableKey()).toBe(false);
  });

  it("returns true for publishable key when present", () => {
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_test_12345";
    expect(hasClerkPublishableKey()).toBe(true);
  });

  it("returns false for isClerkConfigured when secret key is missing", () => {
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_test_12345";
    delete process.env.CLERK_SECRET_KEY;
    expect(isClerkConfigured()).toBe(false);
  });

  it("returns true for isClerkConfigured when both keys are present", () => {
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_test_12345";
    process.env.CLERK_SECRET_KEY = "sk_test_12345";
    expect(isClerkConfigured()).toBe(true);
  });
});
