import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function load(apiBaseUrl: string) {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", apiBaseUrl);
  vi.resetModules();
  const mocks = await import("@/lib/mocks");
  const { useDemoStore } = await import("@/lib/store/demo-store");
  return { mocks, state: useDemoStore.getState() };
}

describe("demoOnly", () => {
  it("returns the fixtures when no API is configured (the offline demo)", async () => {
    const { mocks } = await load("");
    expect(mocks.demoOnly(mocks.matters)).toHaveLength(mocks.matters.length);
    expect(mocks.demoOnly(mocks.matters).length).toBeGreaterThan(0);
  });

  it("returns nothing when the API is configured", async () => {
    const { mocks } = await load("https://app.example.com");
    expect(mocks.demoOnly(mocks.matters)).toEqual([]);
    expect(mocks.demoOnly(mocks.obligations)).toEqual([]);
  });

  it("returns a copy, so callers cannot mutate the fixtures", async () => {
    const { mocks } = await load("");
    expect(mocks.demoOnly(mocks.matters)).not.toBe(mocks.matters);
  });
});

describe("demo store seed", () => {
  it("is fixture-seeded in the offline demo", async () => {
    const { state } = await load("");
    expect(state.matters.length).toBeGreaterThan(0);
    expect(state.documents.length).toBeGreaterThan(0);
    expect(state.facts.length).toBeGreaterThan(0);
    expect(state.auditEvents.length).toBeGreaterThan(0);
  });

  it("starts with no case data when the API is configured", async () => {
    const { state } = await load("https://app.example.com");
    expect(state.matters).toEqual([]);
    expect(state.documents).toEqual([]);
    expect(state.facts).toEqual([]);
    expect(state.checks).toEqual([]);
    expect(state.drafts).toEqual([]);
    expect(state.auditEvents).toEqual([]);
  });

  it("keeps the workflow definitions, which are catalogue content", async () => {
    const { state } = await load("https://app.example.com");
    expect(state.workflows.length).toBeGreaterThan(0);
  });
});
