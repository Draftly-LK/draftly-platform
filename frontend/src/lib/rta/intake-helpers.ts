/**
 * Pure intake helpers for the new-matter screen, kept out of the component so
 * they can be tested without rendering it (TESTING_PLAN.md §3.2).
 */

import { RTA_TAXONOMY } from "@/lib/rta/taxonomy";
import type { MatterType, PhysicalOriginalStatus } from "@/types";
import type { ApiChecklistItem, PartyContext } from "@/types/rta";

/**
 * Q05 option values. `UNKNOWN` is deliberately not a `PartyContext` member —
 * it records that the screening has not been done and must never collapse into
 * `NATURAL_PERSONS_ONLY` (§4.1, §4.4).
 */
export const PARTY_UNKNOWN = "UNKNOWN" as const;
export type PartyAnswer = PartyContext | typeof PARTY_UNKNOWN;

/** `InclusionReason` in compiler.py. Unknown values fall back to the id. */
const INCLUSION_REASON_KEYS: Record<string, string> = {
  BASE: "inclusionBase",
  REGIME: "inclusionRegime",
  EXACT_INSTRUMENT: "inclusionExactInstrument",
  CONDITIONAL_MODULE: "inclusionConditionalModule",
  OFFICE_POLICY: "inclusionOfficePolicy",
  LOCAL_AUTHORITY_POLICY: "inclusionLocalAuthorityPolicy",
  LAWYER_ADDED: "inclusionLawyerAdded",
  RETAINED_AFTER_REVIEW: "inclusionRetainedAfterReview",
};

/**
 * `UNKNOWN` is exclusive: it means the screening has not been done, so it
 * cannot coexist with an asserted party context, and asserting one clears it.
 * Nothing here maps `UNKNOWN` onto `NATURAL_PERSONS_ONLY`.
 */
export function togglePartyContext(
  current: PartyAnswer[],
  answer: PartyAnswer,
): PartyAnswer[] {
  if (current.includes(answer))
    return current.filter((value) => value !== answer);
  if (answer === PARTY_UNKNOWN) return [PARTY_UNKNOWN];
  return [...current.filter((value) => value !== PARTY_UNKNOWN), answer];
}

export function inclusionText(
  item: ApiChecklistItem,
  t: (key: string) => string,
): string {
  const messageKey = INCLUSION_REASON_KEYS[item.inclusionReason];
  const reason =
    messageKey === undefined ? item.inclusionReason : t(messageKey);
  return reason;
}

/**
 * Derive the deprecated M2 `MatterType` for the offline demo store, which still
 * requires it. Reverses the rule pack's own legacy map rather than guessing, and
 * falls back to `other` — the coarse label is never the authority for what the
 * instrument is (§3.6).
 */
export function legacyTypeForSubtype(subtypeId: string | null): MatterType {
  if (subtypeId === null) return "other";
  const match = Object.entries(RTA_TAXONOMY.legacyMatterTypeMap).find(
    ([, mapped]) => mapped === subtypeId,
  );
  const legacy = match?.[0];
  return legacy === "transfer" ||
    legacy === "gift" ||
    legacy === "lease" ||
    legacy === "mortgage"
    ? legacy
    : "other";
}

/**
 * True when the requirement demands a physical original.
 *
 * `physical_original_policy` is the level the requirement demands (§5.4), so
 * only the two ORIGINAL_* levels change what the lawyer must physically
 * produce; NOT_REQUIRED, UNKNOWN and COPY_ONLY do not.
 */
export function demandsOriginal(policy: PhysicalOriginalStatus): boolean {
  return policy === "ORIGINAL_REPORTED" || policy === "ORIGINAL_INSPECTED";
}
