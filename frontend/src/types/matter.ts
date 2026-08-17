import type { Party } from "./party";
import type {
  AutomationScope,
  DispositionScope,
  MatterFamilyId,
  ParcelKind,
  PartyContext,
  RtaMatterState,
  SubtypeDecisionStatus,
  TitleStatus,
} from "./rta";

export type RegistrationRegime = "rta" | "deed" | "condominium" | "special-area";

/**
 * Retired M2 matter vocabulary, kept for migration only.
 *
 * The five values here collapse 22 gazetted instruments plus the statutory
 * processes and registry services into a shape that cannot express what a
 * matter actually is. They are retained because legacy persisted records must
 * stay readable and must be migrated deliberately — never deleted, never
 * guessed at.
 *
 * @deprecated Use `RtaSubtypeId` (see `src/types/rta.ts`) and resolve legacy
 * records with `migrateLegacyMatterType()` from `@/lib/rta/taxonomy`, which
 * always returns a provisional result for a lawyer to confirm.
 */
export type MatterType = "transfer" | "gift" | "lease" | "mortgage" | "other";

export type MatterStatus = "open" | "in-review" | "blocked" | "ready-to-draft" | "closed";
export type NotarialFunction = "examination" | "drafting" | "execution" | "attestation";

export interface MatterProgress { examination: number; drafting: number; execution: number; attestation: number }

export interface Matter {
  id: string;
  reference: string;
  clientReference?: string;
  regime: RegistrationRegime;
  /**
   * Coarse legacy classification. Still required because existing screens read
   * it, but it is derived from `subtypeId` going forward and is never the
   * authority for what instrument the matter is.
   *
   * @deprecated Read `subtypeId` instead.
   */
  type: MatterType;
  parties: Party[];
  status: MatterStatus;
  activeFunction: NotarialFunction;
  progress: MatterProgress;
  ownerId: string;
  createdAt: string;
  updatedAt: string;

  /* ── RTA workflow fields (optional while fixtures catch up) ───────────── */

  /** The exact instrument, e.g. `lk.rta.instrument.transfer_sale` (§3.3). */
  subtypeId?: string;
  /** The lawyer-facing family the subtype sits in (§3.2). */
  familyId?: MatterFamilyId;
  /** Whether the subtype is still provisional or has been confirmed (§12.2). */
  subtypeDecisionStatus?: SubtypeDecisionStatus;
  /** Is the parcel already on an RTA Title Register? (§Executive 1). */
  titleStatus?: TitleStatus;
  /** Ordinary land versus strata (§2.2). */
  parcelKind?: ParcelKind;
  /** Whole parcel, part, or undivided interest (§4.2 Q03). */
  dispositionScope?: DispositionScope;
  /** How much of this matter Draftly may automate (§2.3). */
  automationScope?: AutomationScope;
  /** Position in the RTA matter state machine (§10.1). */
  rtaState?: RtaMatterState;
  /** Non-individual party indicators from Q05 (§4.2). */
  partyContexts?: PartyContext[];
  /** Conditional checklist modules switched on by routing answers (§5.2). */
  activatedConditionalModuleIds?: string[];
  /** Message keys explaining why the matter fell out of V0 automation (§2.3). */
  automationExclusionReasonKeys?: string[];
  /** The checklist snapshot currently shown for this matter (§5.3). */
  activeChecklistSnapshotId?: string;
  /** The retired M2 value this matter was migrated from, if any (§3.6). */
  legacyMatterType?: MatterType;
}
