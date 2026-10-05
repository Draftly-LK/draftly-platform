import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getCase, listCases, searchCases } from "./library";

describe("case API boundary", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("encodes metadata filters and a signed cursor on the catalogue route", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ items: [] }));
    vi.stubGlobal("fetch", fetch);
    await listCases(async () => "synthetic-token", {
      query: "Synthetic & citation",
      collection: "LKCA",
      court: "Synthetic Court",
      year: 1999,
      cursor: "signed+/=",
      limit: 25,
    });
    const [url, init] = fetch.mock.calls[0]!;
    const parsed = new URL(url);
    expect(parsed.pathname).toBe("/api/v1/library/cases");
    expect(Object.fromEntries(parsed.searchParams)).toEqual({
      query: "Synthetic & citation",
      collection: "LKCA",
      court: "Synthetic Court",
      year: "1999",
      limit: "25",
      cursor: "signed+/=",
    });
    expect(init.headers.Authorization).toBe("Bearer synthetic-token");
  });

  it("encodes the reader identity as one path segment", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ item: null }));
    vi.stubGlobal("fetch", fetch);
    await getCase(async () => "synthetic-token", "commonlii-SYNTHETIC/id");
    expect(fetch.mock.calls[0]![0]).toBe(
      "https://api.test/api/v1/library/cases/commonlii-SYNTHETIC%2Fid",
    );
  });

  it("keeps fact patterns out of URLs and sends the retry key with eight-result bound", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ items: [] }));
    vi.stubGlobal("fetch", fetch);
    await searchCases(
      async () => "synthetic-token",
      "Synthetic private facts",
      "logical-search-1",
    );
    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toBe("https://api.test/api/v1/research/cases/search");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      query: "Synthetic private facts",
      limit: 8,
    });
    expect(init.headers["Idempotency-Key"]).toBe("logical-search-1");
  });
});
