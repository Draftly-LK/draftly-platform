import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { API_VERSION_PREFIX, ApiError, apiBaseUrl, apiFetchBlob } from "@/lib/api/client";

const ORIGINAL = process.env.NEXT_PUBLIC_API_BASE_URL;

function setBase(value: string | undefined): void {
  if (value === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = value;
}

beforeEach(() => setBase(undefined));
afterEach(() => setBase(ORIGINAL));

/**
 * The canonical split: base URL is the bare origin, endpoint paths carry
 * `/api/v1`. Getting this wrong in either direction yields a 404 that looks
 * like a backend problem, so both halves are asserted.
 */
describe("apiBaseUrl", () => {
  it("returns null when the backend is not configured", () => {
    expect(apiBaseUrl()).toBeNull();
  });

  it("returns the bare origin unchanged", () => {
    setBase("http://localhost:8000");
    expect(apiBaseUrl()).toBe("http://localhost:8000");
  });

  it("strips a prefix left on the env var rather than doubling it", () => {
    setBase("http://localhost:8000/api/v1");
    expect(apiBaseUrl()).toBe("http://localhost:8000");
  });

  it("ignores trailing slashes in either form", () => {
    setBase("http://localhost:8000/");
    expect(apiBaseUrl()).toBe("http://localhost:8000");
    setBase("http://localhost:8000/api/v1//");
    expect(apiBaseUrl()).toBe("http://localhost:8000");
  });

  it("never yields a base that already contains the version segment", () => {
    for (const value of [
      "http://localhost:8000",
      "http://localhost:8000/",
      "http://localhost:8000/api/v1",
      "http://localhost:8000/api/v1/",
    ]) {
      setBase(value);
      expect(apiBaseUrl()).not.toContain(API_VERSION_PREFIX);
    }
  });
});

const API_DIR = join(process.cwd(), "src", "lib", "api");

describe("endpoint path convention", () => {
  const sources = readdirSync(API_DIR)
    .filter((name) => name.endsWith(".ts") && !name.endsWith(".test.ts"))
    .map((name) => [name, readFileSync(join(API_DIR, name), "utf-8")] as const);

  it.each(sources.map(([name]) => name))(
    "%s never writes a doubled prefix",
    (name) => {
      const source = sources.find(([file]) => file === name)?.[1] ?? "";
      expect(source).not.toContain("/api/v1/api/v1");
    },
  );

  it("every request path starts with the version segment", () => {
    // Catches the mistake this test file exists for: a module that omits the
    // prefix works only while the base URL wrongly supplies it.
    const offenders: string[] = [];
    for (const [name, source] of sources) {
      if (name === "client.ts") continue;
      const calls = source.matchAll(/apiFetch(?:Blob)?<[^>]*>\(\s*(`|")([^`"]*)/g);
      for (const match of calls) {
        const path = match[2] ?? "";
        if (path.startsWith("/") && !path.startsWith(API_VERSION_PREFIX)) {
          offenders.push(`${name}: ${path}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe("apiFetchBlob", () => {
  it("refuses to run when the backend is not configured", async () => {
    await expect(apiFetchBlob("/x", { getToken: async () => "t" })).rejects.toMatchObject({
      code: "api_not_configured",
    });
  });

  it("refuses to run without a session token", async () => {
    setBase("http://api.test");
    const error = await apiFetchBlob("/x", { getToken: async () => null }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, code: "unauthenticated" });
  });

  it("sends the bearer token and returns the body as a blob", async () => {
    setBase("http://api.test");
    const seen: { url: string; auth: string | undefined }[] = [];
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      seen.push({
        url: String(input),
        auth: (init?.headers as Record<string, string>).Authorization,
      });
      return new Response("bytes", { status: 200 });
    }) as typeof fetch;
    try {
      const blob = await apiFetchBlob("/api/v1/artifacts/a", { getToken: async () => "tok" });
      expect(await blob.text()).toBe("bytes");
    } finally {
      globalThis.fetch = original;
    }
    expect(seen).toEqual([{ url: "http://api.test/api/v1/artifacts/a", auth: "Bearer tok" }]);
  });

  it("raises the backend's error for a failed response", async () => {
    setBase("http://api.test");
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ detail: "nope" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    try {
      const error = await apiFetchBlob("/x", { getToken: async () => "tok" }).catch((e) => e);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(404);
    } finally {
      globalThis.fetch = original;
    }
  });
});
