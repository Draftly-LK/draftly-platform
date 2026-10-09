// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { pendingManualIntent, clearManualIntent } from "./mutation-intent";

const request = {
  value: "SYNTHETIC PRIVATE VALUE",
  reason: "SYNTHETIC PRIVATE REASON",
  evidence: { snippet: "SYNTHETIC PRIVATE OCR" },
};
beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe("manual mutation intent metadata", () => {
  it("survives a module reload and identical re-entry without storing private input", async () => {
    const first = await pendingManualIntent("actor-1", "matter-1", request);
    vi.resetModules();
    const reloaded = await import("./mutation-intent");
    const next = await reloaded.pendingManualIntent("actor-1", "matter-1", {
      reason: request.reason,
      evidence: request.evidence,
      value: request.value,
    });
    expect(next.key).toBe(first.key);
    expect(next.persistent).toBe(true);
    const stored = Object.values(sessionStorage).join();
    for (const text of Object.values(request).flatMap((v) =>
      typeof v === "string" ? [v] : [v.snippet],
    ))
      expect(stored).not.toContain(text);
    expect(stored).not.toContain("token");
  });
  it("isolates actors and matters and changed requests", async () => {
    const first = await pendingManualIntent("actor-1", "matter-1", request);
    for (const [actor, matter, body] of [
      ["actor-2", "matter-1", request],
      ["actor-1", "matter-2", request],
      ["actor-1", "matter-1", { ...request, value: "changed" }],
    ] as const)
      expect((await pendingManualIntent(actor, matter, body)).key).not.toBe(
        first.key,
      );
  });
  it("clears success or deliberate new intent without clearing a newer request", async () => {
    const first = await pendingManualIntent("actor-1", "matter-1", request);
    const next = await pendingManualIntent("actor-1", "matter-1", {
      value: "new",
    });
    clearManualIntent(first);
    expect(
      (await pendingManualIntent("actor-1", "matter-1", { value: "new" })).key,
    ).toBe(next.key);
    clearManualIntent(next);
    expect(
      (await pendingManualIntent("actor-1", "matter-1", { value: "new" })).key,
    ).not.toBe(next.key);
  });
  it("expires at the server's 24-hour replay boundary and rejects corrupt metadata", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-09T00:00:00Z"));
    const first = await pendingManualIntent("actor-1", "matter-1", request);
    vi.advanceTimersByTime(24 * 60 * 60 * 1000);
    expect(
      (await pendingManualIntent("actor-1", "matter-1", request)).key,
    ).not.toBe(first.key);
    sessionStorage.setItem(
      first.storageKey,
      '{"version":1,"key":"attacker","createdAt":0}',
    );
    expect(
      (await pendingManualIntent("actor-1", "matter-1", request)).key,
    ).not.toBe("attacker");
  });
  it("keeps retries stable in RAM and reports disabled storage", async () => {
    vi.stubGlobal("sessionStorage", {
      getItem: () => null,
      setItem: () => {
        throw new Error("disabled");
      },
    });
    const first = await pendingManualIntent(
      "actor-disabled",
      "matter-1",
      request,
    );
    const next = await pendingManualIntent(
      "actor-disabled",
      "matter-1",
      request,
    );
    expect(next.key).toBe(first.key);
    expect(next.persistent).toBe(false);
  });
});
