import { describe, expect, it } from "vitest";
import { facts } from "@/lib/mocks";
import en from "./messages/en.json";
import { FACT_LABEL_KEYS, FACT_SECTIONS, factLabelKey } from "./fact-label-keys";

describe("factLabelKey", () => {
  it("strips the namespace off a known key", () => {
    expect(factLabelKey("facts.parcelNo")).toBe("parcelNo");
  });

  it("accepts a key that has no namespace", () => {
    expect(factLabelKey("district")).toBe("district");
  });

  it.each(["facts.syntheticUnknown", "", "facts.", "facts.parcelno"])(
    "falls back to the manual-entry label for %j",
    (labelKey) => {
      expect(factLabelKey(labelKey)).toBe("manualValue");
    },
  );

  it("resolves every seeded fact to a real key, not the fallback", () => {
    const extracted = facts.filter((fact) => fact.section !== "manual");

    for (const fact of extracted) {
      expect(factLabelKey(fact.labelKey), fact.id).not.toBe("manualValue");
    }
  });
});

describe("the key lists", () => {
  it("have no duplicates", () => {
    expect(new Set(FACT_LABEL_KEYS).size).toBe(FACT_LABEL_KEYS.length);
    expect(new Set(FACT_SECTIONS).size).toBe(FACT_SECTIONS.length);
  });

  it("every fact label key has an English message", () => {
    const messages = en.facts as Record<string, unknown>;

    const missing = FACT_LABEL_KEYS.filter((key) => typeof messages[key] !== "string");
    expect(missing).toEqual([]);
  });

  it("every fact section has an English heading", () => {
    const headings = en.sections as Record<string, unknown>;

    const missing = FACT_SECTIONS.filter((section) => typeof headings[section] !== "string");
    expect(missing).toEqual([]);
  });

  it("every seeded fact belongs to a known section", () => {
    const sections = new Set<string>(FACT_SECTIONS);

    expect(facts.filter((fact) => !sections.has(fact.section)).map((f) => f.id)).toEqual([]);
  });
});
