import { describe, expect, it } from "vitest";
import { authorizedKinds, relationForKind } from "./authorization";
import {
  classifyFileName,
  extractIdentityDocument,
  identityDisplayName,
} from "./mock-pipeline";

describe("document authorization", () => {
  it("authorizes identity and deed for RTA transfer", () => {
    expect(authorizedKinds("rta", "transfer")).toEqual(["identity", "deed"]);
    expect(authorizedKinds("rta", "gift")).toEqual([]);
    expect(relationForKind("identity", "rta", "transfer")).toBe("authorized");
    expect(relationForKind("deed", "rta", "transfer")).toBe("authorized");
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
    expect(classifyFileName("nic1f.jpg", "rta", "transfer")).toEqual({
      kind: "identity",
      identitySide: "front",
      relation: "authorized",
    });
    expect(classifyFileName("nic2b.jpeg", "rta", "transfer")).toEqual({
      kind: "identity",
      identitySide: "back",
      relation: "authorized",
    });
  });

  it("marks deeds authorized on transfer and unknown files unclassified", () => {
    expect(classifyFileName("deed-4821.pdf", "rta", "transfer").relation).toBe(
      "authorized",
    );
    expect(classifyFileName("mystery-scan.pdf", "rta", "transfer")).toEqual({
      kind: "other",
      identitySide: "unknown",
      relation: "unclassified",
    });
  });

  it("returns undetected fields without inventing PII", () => {
    const extraction = extractIdentityDocument(
      "doc-1",
      "identity-group-1",
      "front",
    );
    expect(extraction.displayName).toBe("Identity card (unidentified)");
    expect(extraction.extractedText).toBe("");
    expect(extraction.extractedFields.nicNumber).toBeNull();
    expect(extraction.extractedFields.nameEn).toBeNull();
    expect(identityDisplayName("Sample")).toBe("Sample's identity card");
  });
});
