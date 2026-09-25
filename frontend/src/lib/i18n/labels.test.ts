import { describe, expect, it } from "vitest";
import {
  authorityTypeLabels,
  authorityWeightLabels,
  checkLabels,
  courtLevelLabels,
  physicalOriginalLabels,
  sourceFileStateLabels,
  stepLabels,
  verificationLabels,
} from "./labels";

// The maps are typed Record<Union, …>, so the compiler already rejects a
// missing member. What it cannot see is an empty string, or two states that
// read the same: status is never shown by colour alone, so the text must
// tell them apart.
const MAPS = {
  verificationLabels,
  sourceFileStateLabels,
  physicalOriginalLabels,
  checkLabels,
  stepLabels,
  authorityTypeLabels,
  courtLevelLabels,
  authorityWeightLabels,
};

describe.each(Object.entries(MAPS))("%s", (_, labels) => {
  const entries = Object.entries(labels) as [string, { en: string; si: string }][];

  it("has an English and a Sinhala label for every member", () => {
    for (const [, label] of entries) {
      expect(label.en.trim()).not.toBe("");
      expect(label.si.trim()).not.toBe("");
    }
  });

  it("gives every member a distinct English label", () => {
    const english = entries.map(([, label]) => label.en);

    expect(new Set(english).size).toBe(english.length);
  });
});

it("labels every §10.2 source-file state, including the failure states", () => {
  expect(Object.keys(sourceFileStateLabels)).toEqual(
    expect.arrayContaining(["PROCESSING_FAILED", "REJECTED", "SUPERSEDED"]),
  );
});
