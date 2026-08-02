import { describe, expect, it } from "vitest";
import en from "./en.json";
import si from "./si.json";

function keyPaths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return [prefix];
  }

  return Object.entries(value).flatMap(([key, child]) =>
    keyPaths(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe("message catalogues", () => {
  it("keeps the Sinhala scaffold in key parity with English", () => {
    const englishKeys = keyPaths(en).sort();
    const sinhalaKeys = keyPaths(si)
      .filter((key) => key !== "_todo")
      .sort();

    expect(sinhalaKeys).toEqual(englishKeys);
    expect(si._todo).toMatch(/^TODO\(si\):/);
  });
});

