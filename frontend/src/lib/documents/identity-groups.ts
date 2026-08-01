import {
  IDENTITY_FIELD_KEYS,
  type IdentityExtractedFields,
  type IdentitySide,
  type MatterDocument,
  type ProcessingState,
} from "../../types";

export type IdentityFieldSources = Partial<
  Record<keyof IdentityExtractedFields, IdentitySide>
>;

export type DocumentDisplayRow = {
  id: string;
  primary: MatterDocument;
  members: MatterDocument[];
  front?: MatterDocument;
  back?: MatterDocument;
  mergedFields?: IdentityExtractedFields;
  fieldSources?: IdentityFieldSources;
};

const EMPTY_IDENTITY_FIELDS: IdentityExtractedFields = {
  nicNumber: null,
  nameSi: null,
  nameEn: null,
  sex: null,
  dateOfBirth: null,
  addressEn: null,
  serialNumber: null,
  dateOfIssue: null,
  placeOfBirthEn: null,
};

function identityFields(
  document: MatterDocument | undefined,
): IdentityExtractedFields | undefined {
  if (!document?.extractedFields) return undefined;
  return document.extractedFields as IdentityExtractedFields;
}

export function mergeIdentityFields(documents: MatterDocument[]): {
  fields: IdentityExtractedFields;
  sources: IdentityFieldSources;
} {
  const fields = { ...EMPTY_IDENTITY_FIELDS };
  const sources: IdentityFieldSources = {};
  const ordered = [
    ...documents.filter((document) => document.identitySide === "front"),
    ...documents.filter((document) => document.identitySide === "back"),
    ...documents.filter(
      (document) =>
        document.identitySide !== "front" && document.identitySide !== "back",
    ),
  ];

  for (const document of ordered) {
    const extracted = identityFields(document);
    if (!extracted) continue;
    for (const key of IDENTITY_FIELD_KEYS) {
      const value = extracted[key];
      if (fields[key] !== null || value === null || value === undefined)
        continue;
      fields[key] = value;
      sources[key] = document.identitySide ?? "unknown";
    }
  }

  return { fields, sources };
}

export function buildDocumentDisplayRows(
  documents: MatterDocument[],
): DocumentDisplayRow[] {
  const rows: DocumentDisplayRow[] = [];
  const seenGroups = new Set<string>();

  for (const document of documents) {
    if (document.kind !== "identity" || !document.identityGroupId) {
      rows.push({
        id: document.id,
        primary: document,
        members: [document],
        ...(document.kind === "identity"
          ? { mergedFields: mergeIdentityFields([document]).fields }
          : {}),
      });
      continue;
    }

    if (seenGroups.has(document.identityGroupId)) continue;
    seenGroups.add(document.identityGroupId);
    const members = documents.filter(
      (candidate) =>
        candidate.kind === "identity" &&
        candidate.identityGroupId === document.identityGroupId,
    );
    const front = members.find(
      (candidate) => candidate.identitySide === "front",
    );
    const back = members.find((candidate) => candidate.identitySide === "back");
    const merged = mergeIdentityFields(members);
    rows.push({
      id: document.identityGroupId,
      primary: front ?? back ?? document,
      members,
      front,
      back,
      mergedFields: merged.fields,
      fieldSources: merged.sources,
    });
  }

  return rows;
}

export function combinedProcessingState(
  members: MatterDocument[],
): ProcessingState {
  if (members.some((document) => document.processingState === "failed")) {
    return "failed";
  }
  if (members.some((document) => document.processingState === "extracting")) {
    return "extracting";
  }
  if (members.some((document) => document.processingState === "uploaded")) {
    return "uploaded";
  }
  if (members.every((document) => document.processingState === "replaced")) {
    return "replaced";
  }
  return "ready-for-review";
}
