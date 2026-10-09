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

describe("document operation retry metadata", () => {
  it("pins the original precondition across reload and isolates operations", async () => {
    const api = await import("./mutation-intent");
    const first = await api.pendingOperationIntent(
      "retry-actor",
      "matter-1",
      "document:1:refresh",
      {},
      2,
    );
    vi.resetModules();
    const reloaded = await import("./mutation-intent");
    const retry = await reloaded.pendingOperationIntent(
      "retry-actor",
      "matter-1",
      "document:1:refresh",
      {},
      3,
    );
    expect(retry.key).toBe(first.key);
    expect(retry.expectedVersion).toBe(2);
    expect(
      (
        await reloaded.pendingOperationIntent(
          "retry-actor",
          "matter-1",
          "document:1:boundary",
          {},
          3,
        )
      ).key,
    ).not.toBe(first.key);
    reloaded.clearManualIntent(retry);
    const deliberate = await reloaded.pendingOperationIntent(
      "retry-actor",
      "matter-1",
      "document:1:refresh",
      {},
      3,
    );
    expect(deliberate.key).not.toBe(first.key);
    expect(deliberate.expectedVersion).toBe(3);
  });
  it("hashes actual upload bytes and retains no filename or file content", async () => {
    const api = await import("./mutation-intent");
    const file = () =>
      new File(["SYNTHETIC PRIVATE BYTES"], "SYNTHETIC PRIVATE NAME.pdf", {
        type: "application/pdf",
      });
    const first = await api.pendingUploadIntent(
      "upload-actor",
      "matter-1",
      file(),
    );
    vi.resetModules();
    const reloaded = await import("./mutation-intent");
    expect(
      (await reloaded.pendingUploadIntent("upload-actor", "matter-1", file()))
        .key,
    ).toBe(first.key);
    const changed = new File(
      ["DIFFERENT SYNTHETIC BYTES"],
      "SYNTHETIC PRIVATE NAME.pdf",
      { type: "application/pdf" },
    );
    expect(
      (await reloaded.pendingUploadIntent("upload-actor", "matter-1", changed))
        .key,
    ).not.toBe(first.key);
    reloaded.clearManualIntent(first);
    expect(
      (await reloaded.pendingUploadIntent("upload-actor", "matter-1", file()))
        .key,
    ).not.toBe(first.key);
    const stored = Object.values(sessionStorage).join();
    expect(stored).not.toContain("SYNTHETIC");
    expect(stored).not.toContain("application/pdf");
  });
  it("rejects binary containers in the JSON helper instead of treating them as empty objects", async () => {
    for (const body of [
      new File(["one"], "one.pdf"),
      new FormData(),
      { nested: new Blob(["two"]) },
    ])
      await expect(
        pendingManualIntent("actor", "matter", body),
      ).rejects.toThrow();
  });
});

it("deliberate renewal clears a reloaded operation pin without clearing another operation", async () => {
  const intents = await import("./mutation-intent");
  const old = await intents.pendingOperationIntent(
    "renew-actor",
    "renew-matter",
    "inspection",
    request,
    4,
  );
  const other = await intents.pendingOperationIntent(
    "renew-actor",
    "renew-matter",
    "decision",
    request,
    4,
  );
  vi.resetModules();
  const renewed = await import("./mutation-intent");
  renewed.clearPendingOperationIntent(
    "renew-actor",
    "renew-matter",
    "inspection",
  );
  const next = await renewed.pendingOperationIntent(
    "renew-actor",
    "renew-matter",
    "inspection",
    request,
    5,
  );
  expect(next.key).not.toBe(old.key);
  expect(next.expectedVersion).toBe(5);
  expect(
    (
      await renewed.pendingOperationIntent(
        "renew-actor",
        "renew-matter",
        "decision",
        request,
        5,
      )
    ).key,
  ).toBe(other.key);
});
