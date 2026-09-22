/**
 * Records what the `lib/api` accessors send, without a network.
 *
 * `recordFetches()` stubs `fetch` and the API base URL around every test in
 * the calling file and returns the requests seen, so an accessor test can
 * assert the method, URL, headers and body it produced.
 */
import { afterEach, beforeEach, expect, it, vi } from "vitest";

export const API_ORIGIN = "http://api.test";

export interface RecordedRequest {
  method: string;
  /** The URL with the origin removed, e.g. `/api/v1/matters?limit=5`. */
  path: string;
  headers: Record<string, string>;
  /** Parsed JSON, the FormData itself, or undefined when there was no body. */
  body: unknown;
}

export const token = async () => "synthetic-token";

export function recordFetches(responseBody: unknown = {}) {
  const requests: RecordedRequest[] = [];

  beforeEach(() => {
    requests.length = 0;
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", API_ORIGIN);
    vi.stubGlobal(
      "fetch",
      async (input: RequestInfo | URL, init: RequestInit = {}) => {
        const raw = init.body;
        requests.push({
          method: init.method ?? "GET",
          path: String(input).replace(API_ORIGIN, ""),
          headers: { ...(init.headers as Record<string, string>) },
          body: typeof raw === "string" ? JSON.parse(raw) : (raw ?? undefined),
        });
        return new Response(JSON.stringify(responseBody), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  return {
    requests,
    /** The one request the call made; fails if it made none or several. */
    only(): RecordedRequest {
      if (requests.length !== 1) {
        throw new Error(`expected exactly one request, saw ${requests.length}`);
      }
      return requests[0] as RecordedRequest;
    },
  };
}

export interface AccessorCase {
  name: string;
  call: () => Promise<unknown>;
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  body?: unknown;
  /** The version a conditional write must send as `If-Match: "<n>"`. */
  ifMatch?: number;
}

/**
 * One test per accessor: the exact method, path and body, the bearer token,
 * and If-Match on precisely the writes that declare a version.
 */
export function itSendsEach(
  recorder: ReturnType<typeof recordFetches>,
  cases: AccessorCase[],
): void {
  it.each(cases)("$name sends $method $path", async (accessor) => {
    await accessor.call();

    const request = recorder.only();
    expect(request.method).toBe(accessor.method);
    expect(request.path).toBe(accessor.path);
    expect(request.body).toEqual(accessor.body);
    expect(request.headers.Authorization).toBe("Bearer synthetic-token");
    expect(request.headers["If-Match"]).toBe(
      accessor.ifMatch === undefined ? undefined : `"${accessor.ifMatch}"`,
    );
  });
}
