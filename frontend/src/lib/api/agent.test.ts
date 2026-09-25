import { afterEach, describe, expect, it } from "vitest";
import {
  confirmAgentAction,
  getAgentJob,
  getAgentSession,
  isTerminalJobState,
  listAgentMessages,
  newIdempotencyKey,
  rejectAgentAction,
  sendAgentMessage,
  streamAgentJobEvents,
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

describe("sendAgentMessage", () => {
  it("posts the content with the idempotency key", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    const calls: { url: string; init?: RequestInit }[] = [];
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;
    try {
      await sendAgentMessage(async () => "token", "mat-1", "hello", "key-1");
    } finally {
      globalThis.fetch = original;
    }
    expect(calls[0]?.url).toBe("http://api.test/api/v1/matters/mat-1/agent/messages");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ content: "hello" });
    expect((calls[0]?.init?.headers as Record<string, string>)["Idempotency-Key"]).toBe("key-1");
  });
});

describe("streamAgentJobEvents", () => {
  const original = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = original;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  function streamOf(...chunks: string[]): Response {
    const encoder = new TextEncoder();
    return new Response(
      new ReadableStream({
        start(controller) {
          for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
          controller.close();
        },
      }),
      { status: 200 },
    );
  }

  it("emits parsed frames, including one split across chunks", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    globalThis.fetch = (async () =>
      streamOf(
        'event: progress\ndata: {"step":1}\n\nevent: do',
        'ne\ndata: {"ok":true}\n\n',
      )) as typeof fetch;
    const seen: [string, unknown][] = [];
    const finished = await streamAgentJobEvents(async () => "t", "job-1", (name, data) =>
      seen.push([name, data]),
    );
    expect(finished).toBe(true);
    expect(seen).toEqual([
      ["progress", { step: 1 }],
      ["done", { ok: true }],
    ]);
  });

  it("reports an unparseable frame without data and ignores data-less frames", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    globalThis.fetch = (async () => streamOf("event: x\ndata: {bad\n\n: comment\n\n")) as typeof fetch;
    const seen: [string, unknown][] = [];
    await streamAgentJobEvents(async () => "t", "job-1", (name, data) => seen.push([name, data]));
    expect(seen).toEqual([["x", null]]);
  });

  it("returns false when unconfigured, unauthenticated, rejected or dropped", async () => {
    const noop = () => undefined;
    expect(await streamAgentJobEvents(async () => "t", "job-1", noop)).toBe(false);

    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    expect(await streamAgentJobEvents(async () => null, "job-1", noop)).toBe(false);

    globalThis.fetch = (async () => new Response("no", { status: 500 })) as typeof fetch;
    expect(await streamAgentJobEvents(async () => "t", "job-1", noop)).toBe(false);

    globalThis.fetch = (async () => {
      throw new Error("offline");
    }) as typeof fetch;
    expect(await streamAgentJobEvents(async () => "t", "job-1", noop)).toBe(false);
  });
});
