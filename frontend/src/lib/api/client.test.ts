import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { API_VERSION_PREFIX, apiBaseUrl } from "@/lib/api/client";

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
