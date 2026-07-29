import { describe, expect, it } from "vitest";
import { authorizedKinds, relationForKind } from "./authorization";
import {
  classifyFileName,
  extractIdentityDocument,
  identityDisplayName,
} from "./mock-pipeline";

describe("document authorization", () => {
  it("authorizes only identity for RTA transfer", () => {
    expect(authorizedKinds("rta", "transfer")).toEqual(["identity"]);
    expect(authorizedKinds("rta", "gift")).toEqual([]);
    expect(relationForKind("identity", "rta", "transfer")).toBe("authorized");
    expect(relationForKind("deed", "rta", "transfer")).toBe("unrelated");
    expect(relationForKind("other", "rta", "transfer")).toBe("unclassified");
  });
});

describe("mock classify and extract", () => {
  it("classifies identity front and back from filenames", () => {
    expect(classifyFileName("nic-front-scan.pdf", "rta", "transfer")).toEqual({
      kind: "identity",
      identitySide: "front",
      relation: "authorized",
    });
    expect(classifyFileName("identity-back.png", "rta", "transfer")).toEqual({
      kind: "identity",
      identitySide: "back",
      relation: "authorized",
    });
  });

  it("marks deeds unrelated on transfer and unknown files unclassified", () => {
    expect(classifyFileName("deed-4821.pdf", "rta", "transfer").relation).toBe(
      "unrelated",
    );
    expect(classifyFileName("mystery-scan.pdf", "rta", "transfer")).toEqual({
      kind: "other",
      identitySide: "unknown",
      relation: "unclassified",
    });
  });

  it("renames identity extracts with synthetic person names", () => {
    const extraction = extractIdentityDocument(
      "doc-1",
      "identity-group-1",
      "front",
    );
    expect(extraction.displayName).toBe(
      identityDisplayName("A. B. Perera (synthetic)"),
    );
    expect(extraction.extractedFields.idReference).toMatch(/^ID-SYN-\d{4}$/);
    expect(extraction.extractedText).toContain("Full name:");
  });
});
