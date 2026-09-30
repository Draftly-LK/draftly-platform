import { describe, expect, it } from "vitest";
import { countFilled, fieldStatus, isUnresolved, printedValue } from "./field-state";
import { loadSlotValues, saveSlotValues } from "./slot-storage";

const unresolved = { displayValue: "[[UNRESOLVED: district]]", awaitingConfirmation: false };
const awaiting = { displayValue: "Synthetic District", awaitingConfirmation: true };
const confirmed = { displayValue: "Synthetic District", awaitingConfirmation: false };

describe("field state", () => {
  it("reads the unresolved token, never an empty value", () => {
    expect(isUnresolved(unresolved)).toBe(true);
    expect(isUnresolved(confirmed)).toBe(false);
    expect(printedValue(unresolved)).toBeNull();
    expect(printedValue(confirmed)).toBe("Synthetic District");
  });

  it("reports unresolved, awaiting, and confirmed", () => {
    expect(fieldStatus(unresolved)).toBe("unresolved");
    expect(fieldStatus(awaiting)).toBe("awaiting");
    expect(fieldStatus(confirmed)).toBe("confirmed");
  });

  it("counts a blank as filled from its field or its typed text", () => {
    const slots = [
      { id: "a", field: "district" },
      { id: "b", field: "missing" },
      { id: "c", field: "unresolved" },
      { id: "d", field: null },
      { id: "e", field: null },
    ];
    const fields = { district: confirmed, unresolved };
    expect(countFilled(slots, fields, { d: "written", e: "   " })).toBe(2);
  });
});

class MemoryStorage {
  private items = new Map<string, string>();
  getItem(key: string) {
    return this.items.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.items.set(key, value);
  }
}

describe("slot storage", () => {
  it("round-trips string values per form", () => {
    const storage = new MemoryStorage() as unknown as Storage;
    expect(saveSlotValues("form-1", { "f08.7": "Synthetic condition" }, storage)).toBe(true);
    expect(loadSlotValues("form-1", storage)).toEqual({ "f08.7": "Synthetic condition" });
    expect(loadSlotValues("form-2", storage)).toEqual({});
  });

  it("drops malformed or non-string entries", () => {
    const storage = new MemoryStorage() as unknown as Storage;
    storage.setItem("draftly.gazette.slots.v1.bad", "{not json");
    storage.setItem("draftly.gazette.slots.v1.list", "[1,2]");
    storage.setItem("draftly.gazette.slots.v1.mixed", JSON.stringify({ a: "ok", b: 3 }));
    expect(loadSlotValues("bad", storage)).toEqual({});
    expect(loadSlotValues("list", storage)).toEqual({});
    expect(loadSlotValues("mixed", storage)).toEqual({ a: "ok" });
  });

  it("treats unavailable storage as empty", () => {
    const throwing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    } as unknown as Storage;
    expect(loadSlotValues("form-1", throwing)).toEqual({});
    expect(saveSlotValues("form-1", {}, throwing)).toBe(false);
    expect(saveSlotValues("form-1", {}, undefined)).toBe(false);
    expect(loadSlotValues("form-1", undefined)).toEqual({});
  });
});
