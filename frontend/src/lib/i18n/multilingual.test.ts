import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isMultilingualEnabled } from "./multilingual";

describe("multilingual language support flag", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("defaults to enabled when MULTILINGUAL_LANGUAGE_SUPPORT is unset", () => {
    delete process.env.MULTILINGUAL_LANGUAGE_SUPPORT;
    expect(isMultilingualEnabled()).toBe(true);
  });

  it("is enabled when MULTILINGUAL_LANGUAGE_SUPPORT=true", () => {
    process.env.MULTILINGUAL_LANGUAGE_SUPPORT = "true";
    expect(isMultilingualEnabled()).toBe(true);
  });

  it("is disabled only for the exact value false", () => {
    process.env.MULTILINGUAL_LANGUAGE_SUPPORT = "false";
    expect(isMultilingualEnabled()).toBe(false);
  });
});
