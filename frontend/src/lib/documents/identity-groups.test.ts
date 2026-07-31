import { describe, expect, it } from "vitest";
import {
  buildDocumentDisplayRows,
  mergeIdentityFields,
} from "./identity-groups";
import type {
  IdentityExtractedFields,
  IdentitySide,
  MatterDocument,
} from "../../types";

const emptyFields = (): IdentityExtractedFields => ({
  nicNumber: null,
  nameSi: null,
  nameEn: null,
  sex: null,
  dateOfBirth: null,
  addressEn: null,
  serialNumber: null,
  dateOfIssue: null,
  placeOfBirthEn: null,
});

function identityDocument(
  id: string,
  side: IdentitySide,
  fields: Partial<IdentityExtractedFields>,
): MatterDocument {
  return {
    id,
    matterId: "matter-synthetic",
    fileName: `${id}.jpg`,
    kind: "identity",
    language: "en",
    pageCount: 1,
    processingState: "ready-for-review",
    qualityProblems: [],
    versions: [],
    uploadedAt: "2026-07-22T10:00:00.000Z",
    relation: "authorized",
    identitySide: side,
    identityGroupId: "identity-group-1",
    extractedFields: { ...emptyFields(), ...fields },
  };
}

describe("identity document groups", () => {
  it("merges complementary front and back fields without inventing values", () => {
    const front = identityDocument("front", "front", {
      nameEn: "Synthetic Person",
      nicNumber: "SYNTHETIC-ID",
    });
    const back = identityDocument("back", "back", {
      addressEn: "Synthetic address",
      dateOfIssue: "2026-01-01",
    });

    const merged = mergeIdentityFields([front, back]);

    expect(merged.fields.nameEn).toBe("Synthetic Person");
    expect(merged.fields.addressEn).toBe("Synthetic address");
    expect(merged.fields.placeOfBirthEn).toBeNull();
    expect(merged.sources.nameEn).toBe("front");
    expect(merged.sources.addressEn).toBe("back");
  });

  it("renders a paired front and back as one logical display row", () => {
    const front = identityDocument("front", "front", {});
    const back = identityDocument("back", "back", {});

    const rows = buildDocumentDisplayRows([front, back]);

    expect(rows).toHaveLength(1);
    expect(rows[0]?.front?.id).toBe("front");
    expect(rows[0]?.back?.id).toBe("back");
    expect(rows[0]?.members).toHaveLength(2);
  });
});
