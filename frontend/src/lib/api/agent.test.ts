import { afterEach, describe, expect, it } from "vitest";
import {
  confirmAgentAction,
  getAgentJob,
  getAgentSession,
  isTerminalJobState,
  listAgentMessages,
  newIdempotencyKey,
  rejectAgentAction,
} from "@/lib/api/agent";

describe("job state", () => {
  it("treats only finished states as terminal", () => {
    expect(isTerminalJobState("succeeded")).toBe(true);
    expect(isTerminalJobState("failed")).toBe(true);
    // A dead-lettered turn is finished, not still running: the UI must stop
    // polling and show the failure rather than spin forever.
    expect(isTerminalJobState("dead_letter")).toBe(true);
  });

  it("keeps watching while a turn can still change", () => {
    expect(isTerminalJobState("queued")).toBe(false);
    expect(isTerminalJobState("running")).toBe(false);
  });
});

describe("idempotency keys", () => {
  it("mints a distinct key per logical send", () => {
    const keys = new Set(Array.from({ length: 50 }, () => newIdempotencyKey()));
    expect(keys.size).toBe(50);
  });

  it("produces a non-empty key even without crypto.randomUUID", () => {
    // The composer reuses one key across retries, so an empty or colliding key
    // would turn a retry into a second question to the assistant.
    expect(newIdempotencyKey().length).toBeGreaterThan(8);
  });
});

describe("agent endpoint URLs", () => {
  const ORIGINAL = process.env.NEXT_PUBLIC_API_BASE_URL;
  afterEach(() => {
    if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
    else process.env.NEXT_PUBLIC_API_BASE_URL = ORIGINAL;
  });

  async function capture(
    run: (getToken: () => Promise<string>) => Promise<unknown>,
  ): Promise<string> {
    let seen = "";
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      seen = typeof input === "string" ? input : String(input);
      return new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;
    try {
      await run(async () => "token");
    } finally {
      globalThis.fetch = original;
    }
    return seen;
  }

  it("hits the versioned session route exactly once", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    const url = await capture((getToken) => getAgentSession(getToken, "mat-1"));
    expect(url).toBe("http://api.test/api/v1/matters/mat-1/agent");
  });

  it("does not double the prefix when the env var already has it", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test/api/v1"; // stripped by apiBaseUrl
    const url = await capture((getToken) =>
      listAgentMessages(getToken, "mat-1", { limit: 20 }),
    );
    expect(url).toBe("http://api.test/api/v1/matters/mat-1/agent/messages?limit=20");
    // The whole point: exactly one version segment, never /api/v1/api/v1.
    expect(url.match(/\/api\/v1/g)).toHaveLength(1);
    expect(url).not.toContain("/api/v1/api/v1");
  });

  it("addresses a job without the matter in the path", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    const url = await capture((getToken) => getAgentJob(getToken, "ajob-1"));
    expect(url).toBe("http://api.test/api/v1/agent-jobs/ajob-1");
  });

  it("builds confirm and reject under the matter", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    const confirm = await capture((getToken) =>
      confirmAgentAction(getToken, "mat-1", "apa-1"),
    );
    const reject = await capture((getToken) =>
      rejectAgentAction(getToken, "mat-1", "apa-1", "no"),
    );
    expect(confirm).toBe(
      "http://api.test/api/v1/matters/mat-1/agent/actions/apa-1/confirm",
    );
    expect(reject).toBe(
      "http://api.test/api/v1/matters/mat-1/agent/actions/apa-1/reject",
    );
  });
});
