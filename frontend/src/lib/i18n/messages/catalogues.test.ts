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

function readPath(root: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((value, segment) => {
    if (typeof value !== "object" || value === null) return undefined;
    return (value as Record<string, unknown>)[segment];
  }, root);
}

/** P0 demo-path keys that must be native Sinhala (not English clones). */
const essentialTranslatedKeys = [
  "shell.home",
  "shell.matters",
  "shell.create",
  "matterNav.documents",
  "matterNav.facts",
  "home.title",
  "home.commandTitle",
  "matters.title",
  "documents.title",
  "documents.upload",
  "facts.verify",
  "facts.title",
  "workflow.title",
  "checks.title",
  "draft.newDraft",
  "newMatter.chooseRegime",
  "overview.continue",
  "settings.title",
  "library.title",
  "help.title",
] as const;

/** Intentional shared tokens (brand, shortcuts, acronyms, placeholders). */
const intentionalSharedKeys = new Set([
  "app.name",
  "shell.searchShortcut",
  "shell.english",
  "shell.sinhala",
  "matterNav.regime",
  "placeholder.title",
  "matters.rta",
  "documents.replacementFileName",
  "workflow.rta",
  "draft.legalPlaceholder",
  "activity.event",
  "activity.target",
  "newMatter.entryTitle",
  "newMatter.rdo",
  "newMatter.rta",
  "newMatter.matterPlaceholder",
  "newMatter.clientPlaceholder",
  "newMatter.detectedAs",
  "settings.registration",
]);

describe("message catalogues", () => {
  it("keeps the Sinhala catalogue in key parity with English", () => {
    const englishKeys = keyPaths(en).sort();
    const sinhalaKeys = keyPaths(si)
      .filter((key) => key !== "_todo")
      .sort();

    expect(sinhalaKeys).toEqual(englishKeys);
    expect(si._todo).toMatch(/^TODO\(si\):/);
  });

  it("translates essential demo-path keys into Sinhala", () => {
    for (const key of essentialTranslatedKeys) {
      const english = readPath(en as Record<string, unknown>, key);
      const sinhala = readPath(si as Record<string, unknown>, key);
      expect(sinhala, key).toEqual(expect.any(String));
      expect(sinhala, key).not.toEqual(english);
      expect(String(sinhala), key).toMatch(/\p{Script=Sinhala}/u);
    }
  });

  it("keeps only intentional Latin tokens identical across locales", () => {
    const englishLeaves = keyPaths(en).filter((key) => {
      const value = readPath(en as Record<string, unknown>, key);
      return typeof value === "string";
    });

    const identical = englishLeaves.filter((key) => {
      const english = readPath(en as Record<string, unknown>, key);
      const sinhala = readPath(si as Record<string, unknown>, key);
      return english === sinhala;
    });

    expect(identical.sort()).toEqual([...intentionalSharedKeys].sort());
  });
});
