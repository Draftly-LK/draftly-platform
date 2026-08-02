/**
 * Every fact label key under the `facts` namespace, in one place.
 *
 * Screens resolve a fact's label by stripping the namespace off
 * `VerifiedFact.labelKey`, which needs a literal union to type-check against
 * next-intl. Keeping that union here stops it drifting between the facts and
 * documents screens, which previously each carried their own copy.
 */
export const FACT_LABEL_KEYS = [
  // Land parcel particulars
  "district",
  "dsDivision",
  "gnDivision",
  "village",
  "assessmentNumber",
  "cadastralMapNo",
  "blockNo",
  "sheetNo",
  "parcelNo",
  "extent",
  "extentSubjectToTransfer",
  "landName",
  // Prior registration reference
  "placeOfRegistration",
  "titleCertificateNo",
  "classOfTitle",
  // Survey plan
  "surveyPlanNo",
  "surveyorName",
  "surveyorRegistration",
  "lotNo",
  "boundaryNorth",
  "boundaryEast",
  "boundarySouth",
  "boundaryWest",
  // Transferor
  "transferorName",
  "transferorRegistration",
  "transferorAddress",
  "transferorAuthority",
  "transferorSignatories",
  // Transferee
  "transfereeName",
  "transfereeNic",
  "transfereeAddress",
  // Consideration
  "consideration",
  "considerationWords",
  "paymentReceived",
  "paymentBalance",
  // Execution
  "notaryName",
  "notaryCode",
  "priorInstrumentConsideration",
  // Facts entered by hand when extraction cannot supply a value
  "manualValue",
] as const;

export type FactLabelKey = (typeof FACT_LABEL_KEYS)[number];

const KNOWN = new Set<string>(FACT_LABEL_KEYS);

/**
 * Turns `"facts.parcelNo"` into `"parcelNo"`, falling back to the
 * manual-entry label so an unrecognised key renders as text rather than a
 * next-intl missing-message error.
 */
export function factLabelKey(labelKey: string): FactLabelKey {
  const key = labelKey.split(".").at(-1) ?? "";
  return KNOWN.has(key) ? (key as FactLabelKey) : "manualValue";
}

/** Fact sections, used as headings in the drafting output and review screens. */
export const FACT_SECTIONS = [
  "parcel",
  "title",
  "survey",
  "transferor",
  "transferee",
  "consideration",
  "execution",
  "manual",
] as const;

export type FactSection = (typeof FACT_SECTIONS)[number];
