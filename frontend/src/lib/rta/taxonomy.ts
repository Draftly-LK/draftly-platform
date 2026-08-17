/**
 * Typed accessors over the generated RTA taxonomy.
 *
 * `taxonomy.generated.json` is exported from the Python rule pack
 * (`backend/src/modules/content_governance/domain/rta/`) by
 * `backend/scripts/export_rta_contracts.py` and is validated against the Python
 * definitions by a backend contract test. Do not edit the JSON here, and do not
 * add taxonomy facts to this file: this module only reads, sorts, and filters.
 *
 * Nothing here decides anything legal. Choosing a subtype is always a lawyer's
 * decision (§3.5); these helpers just present the closed vocabulary.
 */

import type {
  MatterFamilyId,
  RtaConditionalModuleDefinition,
  RtaFamilyDefinition,
  RtaRegimeId,
  RtaSubtypeDefinition,
  RtaSubtypeId,
  RtaTaxonomyContract,
} from "@/types/rta";
import contract from "./taxonomy.generated.json";

/**
 * The single cast in the module.
 *
 * TypeScript infers the JSON literal's types structurally (`string` for every
 * enum member, `never[]` for empty arrays), which cannot be assigned to the
 * contract interface directly. The values are nonetheless guaranteed to match:
 * the file is generated from the Python source of truth, where each of these
 * fields is a closed `enum`, and a backend contract test fails the build if the
 * export drifts from those enums. Casting once here keeps the rest of the
 * frontend fully typed.
 */
export const RTA_TAXONOMY = contract as unknown as RtaTaxonomyContract;

/** The only regime with a rule pack (§3.1). */
export const RTA_REGIME_ID: RtaRegimeId = RTA_TAXONOMY.regimeId;

function byOrder<T extends { order: number }>(a: T, b: T): number {
  return a.order - b.order;
}

/** Every family, in display order. */
export function families(): RtaFamilyDefinition[] {
  return [...RTA_TAXONOMY.families].sort(byOrder);
}

/** The families that describe a dealing a lawyer initiates (§3.2). */
export function transactionFamilies(): RtaFamilyDefinition[] {
  return families().filter((family) => family.isTransactionFamily);
}

/**
 * Title settlement, dispute/rectification, and controlled-other.
 *
 * Kept separate from the transaction families on purpose: they are not things a
 * lawyer picks from the "what are you doing?" list, and presenting them there
 * would invite mis-routing.
 */
export function statutoryFamilies(): RtaFamilyDefinition[] {
  return families().filter((family) => !family.isTransactionFamily);
}

/** Every subtype — instruments, statutory processes, and registry services. */
export function allSubtypes(): RtaSubtypeDefinition[] {
  return [...RTA_TAXONOMY.subtypes].sort(byOrder);
}

/** The 22 gazetted forms (§3.4). */
export function prescribedInstruments(): RtaSubtypeDefinition[] {
  return allSubtypes().filter((subtype) => subtype.kind === "PRESCRIBED_INSTRUMENT");
}

export function subtypesInFamily(familyId: MatterFamilyId): RtaSubtypeDefinition[] {
  return allSubtypes().filter((subtype) => subtype.familyId === familyId);
}

export function getSubtype(id: RtaSubtypeId): RtaSubtypeDefinition | undefined {
  return RTA_TAXONOMY.subtypes.find((subtype) => subtype.id === id);
}

/** Checklist modules activated by routing answers rather than by subtype (§5.2). */
export function conditionalModules(): RtaConditionalModuleDefinition[] {
  return [...RTA_TAXONOMY.conditionalModules];
}

export function getConditionalModule(id: string): RtaConditionalModuleDefinition | undefined {
  return RTA_TAXONOMY.conditionalModules.find((definition) => definition.id === id);
}

/** Subtypes Draftly automates end-to-end today (§2.2). */
export function v0SubtypeIds(): RtaSubtypeId[] {
  return allSubtypes()
    .filter((subtype) => subtype.releaseTier === "V0")
    .map((subtype) => subtype.id);
}

export function isV0Subtype(id: RtaSubtypeId): boolean {
  return getSubtype(id)?.releaseTier === "V0";
}

/** What `migrateLegacyMatterType` returns when the legacy value is mapped. */
export interface LegacyMatterTypeMigration {
  subtypeId: RtaSubtypeId;
  familyId: MatterFamilyId;
  /**
   * Always `true`. A migration is a guess about an old record, so the resulting
   * subtype is `PROVISIONAL` until the responsible lawyer confirms it (§3.6).
   */
  needsLawyerConfirmation: true;
}

/**
 * Map a retired M2 `MatterType` onto an RTA subtype (§3.6).
 *
 * Returns `null` for anything not in the map. It must never fall back to
 * `other_declared_instrument`: that subtype requires a declared legal basis and
 * silently routing an unrecognised value there would manufacture a legal
 * assertion nobody made.
 */
export function migrateLegacyMatterType(legacy: string): LegacyMatterTypeMigration | null {
  const subtypeId = RTA_TAXONOMY.legacyMatterTypeMap[legacy];
  if (subtypeId === undefined) return null;

  const subtype = getSubtype(subtypeId);
  if (subtype === undefined) return null;

  return { subtypeId: subtype.id, familyId: subtype.familyId, needsLawyerConfirmation: true };
}

/** next-intl message key for a subtype's lawyer-facing label. */
export function subtypeLabelKey(id: RtaSubtypeId): string | undefined {
  return getSubtype(id)?.labelKey;
}

/** next-intl message key for a family's lawyer-facing label. */
export function familyLabelKey(id: MatterFamilyId): string | undefined {
  return RTA_TAXONOMY.families.find((family) => family.id === id)?.labelKey;
}
