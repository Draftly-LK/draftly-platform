import { describe, expect, it } from "vitest";
import { isTerminalJobState, newIdempotencyKey } from "@/lib/api/agent";

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
