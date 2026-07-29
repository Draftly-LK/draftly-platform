import { relationForKind } from "./authorization";
import type {
  DocumentKind,
  DocumentRelation,
  IdentityExtractedFields,
  IdentitySide,
  MatterType,
  RegistrationRegime,
} from "@/types";

/** Synthetic person tokens for identity rename — never real client names. */
export const SYNTHETIC_IDENTITY_PERSONS = [
  "A. B. Perera (synthetic)",
  "C. D. Fernando (synthetic)",
  "E. F. Jayasuriya (synthetic)",
  "G. H. Wijesinghe (synthetic)",
] as const;

export type IdentityPairAssignment = {
  documentId: string;
  identityGroupId: string;
  identitySide: IdentitySide;
};

export type ClassifyResult = {
  kind: DocumentKind;
  identitySide: IdentitySide;
  relation: DocumentRelation;
};

export type ExtractionResult = {
  extractedText: string;
  extractedFields: IdentityExtractedFields;
  displayName: string;
  fileName: string;
  language: "en" | "si" | "mixed";
};

const KNOWN_KIND_PATTERNS: Array<{ kind: DocumentKind; pattern: RegExp }> = [
  { kind: "deed", pattern: /\bdeed\b/i },
  { kind: "survey-plan", pattern: /\b(survey[-_]?plan|plan)\b/i },
  { kind: "assessment", pattern: /\bassessment\b/i },
  { kind: "registry-extract", pattern: /\b(registry|extract)\b/i },
  { kind: "at-form", pattern: /\bat[-_]?form\b/i },
];

function normalizeName(fileName: string): string {
  return fileName.toLowerCase().replace(/\.[^.]+$/, "");
}

/** Mock classifier from filename heuristics. Deterministic; no OCR. */
// TODO(api): POST /api/documents/classify
export function classifyFileName(
  fileName: string,
  regime: RegistrationRegime,
  type: MatterType,
): ClassifyResult {
  const base = normalizeName(fileName);
  const isIdentity =
    /\b(identity|id[-_]?card|nic)\b/i.test(base) ||
    /^id[-_]/.test(base) ||
    /[-_]id$/.test(base) ||
    /[-_]id[-_]/.test(base);

  if (isIdentity) {
    let identitySide: IdentitySide = "unknown";
    if (/\b(front|obverse)\b/i.test(base)) identitySide = "front";
    else if (/\b(back|reverse)\b/i.test(base)) identitySide = "back";
    return {
      kind: "identity",
      identitySide,
      relation: relationForKind("identity", regime, type),
    };
  }

  for (const { kind, pattern } of KNOWN_KIND_PATTERNS) {
    if (pattern.test(base)) {
      return {
        kind,
        identitySide: "unknown",
        relation: relationForKind(kind, regime, type),
      };
    }
  }

  return {
    kind: "other",
    identitySide: "unknown",
    relation: relationForKind("other", regime, type),
  };
}

export function personForIdentityGroup(identityGroupId: string): string {
  const match = /group-(\d+)/.exec(identityGroupId);
  const index = match ? Number(match[1]) - 1 : 0;
  const safeIndex =
    ((index % SYNTHETIC_IDENTITY_PERSONS.length) +
      SYNTHETIC_IDENTITY_PERSONS.length) %
    SYNTHETIC_IDENTITY_PERSONS.length;
  return SYNTHETIC_IDENTITY_PERSONS[safeIndex] ?? SYNTHETIC_IDENTITY_PERSONS[0];
}

export function identityDisplayName(personName: string): string {
  return `${personName}'s identity card`;
}

export function identityFileName(
  personName: string,
  side: IdentitySide,
): string {
  const slug = personName
    .toLowerCase()
    .replace(/\(synthetic\)/g, "synthetic")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  const sideSuffix =
    side === "front" ? "-front" : side === "back" ? "-back" : "";
  return `${slug}-identity${sideSuffix}.pdf`;
}

function opaqueIdReference(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) % 10000;
  }
  return `ID-SYN-${String(4100 + (hash % 5000)).padStart(4, "0")}`;
}

/** Seeded extraction payload for identity cards. No real NIC digits. */
// TODO(api): POST /api/matters/{matterId}/documents/{documentId}/extract
export function extractIdentityDocument(
  documentId: string,
  identityGroupId: string,
  side: IdentitySide,
): ExtractionResult {
  const person = personForIdentityGroup(identityGroupId);
  const idReference = opaqueIdReference(identityGroupId);
  const fields: IdentityExtractedFields = {
    fullName: person,
    idReference,
    address: "12 Synthetic Lane, Colombo (synthetic)",
    dateOfBirth: "1978-03-14 (synthetic)",
  };
  const sideLabel =
    side === "front" ? "Front" : side === "back" ? "Back" : "Side unknown";
  const extractedText = [
    `National Identity Card — ${sideLabel} (synthetic extract)`,
    "",
    `Full name: ${fields.fullName}`,
    `Identity reference: ${fields.idReference}`,
    `Address: ${fields.address}`,
    `Date of birth: ${fields.dateOfBirth}`,
    "",
    "This text is a seeded mock extraction for interface review.",
    "Correct any OCR-like errors before verifying facts.",
  ].join("\n");

  return {
    extractedText,
    extractedFields: fields,
    displayName: identityDisplayName(person),
    fileName: identityFileName(person, side),
    language: "en",
  };
}

export function nextIdentityGroupId(existingGroupIds: string[]): string {
  const used = new Set(
    existingGroupIds
      .map((id) => {
        const match = /group-(\d+)/.exec(id);
        return match ? Number(match[1]) : 0;
      })
      .filter((n) => n > 0),
  );
  let n = 1;
  while (used.has(n)) n += 1;
  return `identity-group-${n}`;
}
