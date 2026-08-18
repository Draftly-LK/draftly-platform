/**
 * The RTA workflow catalogue, derived from the generated taxonomy.
 *
 * One workflow per RTA subtype: the taxonomy is the source of truth for which
 * instruments exist, which family they belong to, which Gazette form they use,
 * and how much of each is automated in this release. Nothing here is authored —
 * adding a subtype to the rule pack adds a workflow to this catalogue.
 *
 * Distinct from `lib/mocks` `workflows`, which are the seeded *runnable*
 * procedures with steps for the demonstration matter. This catalogue answers
 * "what RTA work can this product describe?"; a runnable workflow answers
 * "what are the steps for this matter?".
 */

import {
  allSubtypes,
  families,
  isV0Subtype,
  subtypesInFamily,
} from "@/lib/rta/taxonomy";
import type {
  MatterFamilyId,
  RtaFamilyDefinition,
  RtaSubtypeDefinition,
} from "@/types/rta";

export interface RtaWorkflow {
  subtype: RtaSubtypeDefinition;
  family: RtaFamilyDefinition;
  /** True when Draftly prepares this instrument in the current release. */
  available: boolean;
}

export interface RtaWorkflowFamilyGroup {
  family: RtaFamilyDefinition;
  workflows: RtaWorkflow[];
}

/**
 * Editorial ordering for the dashboard, not a measurement.
 *
 * There is no usage telemetry yet, so this is the team's view of the work a
 * notarial practice meets most often, narrowed to instruments the taxonomy
 * marks as prescribed. Reorder freely; replace with real counts once the
 * matter store can report them.
 */
const COMMON_SUBTYPE_IDS: readonly string[] = [
  "lk.rta.instrument.transfer_sale",
  "lk.rta.instrument.mortgage",
  "lk.rta.instrument.mortgage_cancel",
  "lk.rta.instrument.lease",
  "lk.rta.instrument.gift",
  "lk.rta.instrument.sale_agreement",
];

function toWorkflow(
  subtype: RtaSubtypeDefinition,
  familyById: Map<MatterFamilyId, RtaFamilyDefinition>,
): RtaWorkflow | null {
  const family = familyById.get(subtype.familyId);
  if (family === undefined) return null;
  return { subtype, family, available: isV0Subtype(subtype.id) };
}

function familyIndex(): Map<MatterFamilyId, RtaFamilyDefinition> {
  return new Map(families().map((family) => [family.id, family]));
}

/** Every RTA workflow, in taxonomy order. */
export function rtaWorkflows(): RtaWorkflow[] {
  const familyById = familyIndex();
  return allSubtypes()
    .map((subtype) => toWorkflow(subtype, familyById))
    .filter((workflow): workflow is RtaWorkflow => workflow !== null);
}

/** Grouped by family, in family order; families with no subtypes are dropped. */
export function rtaWorkflowsByFamily(): RtaWorkflowFamilyGroup[] {
  const familyById = familyIndex();
  return families()
    .map((family) => ({
      family,
      workflows: subtypesInFamily(family.id)
        .map((subtype) => toWorkflow(subtype, familyById))
        .filter((workflow): workflow is RtaWorkflow => workflow !== null),
    }))
    .filter((group) => group.workflows.length > 0);
}

/**
 * The dashboard shortlist, in `COMMON_SUBTYPE_IDS` order.
 *
 * Ids that no longer exist in the taxonomy are skipped rather than throwing, so
 * a rule-pack change cannot break the dashboard.
 */
export function commonRtaWorkflows(limit = COMMON_SUBTYPE_IDS.length): RtaWorkflow[] {
  const bySubtypeId = new Map(rtaWorkflows().map((workflow) => [workflow.subtype.id, workflow]));
  return COMMON_SUBTYPE_IDS.map((id) => bySubtypeId.get(id))
    .filter((workflow): workflow is RtaWorkflow => workflow !== undefined)
    .slice(0, limit);
}

export function availableRtaWorkflowCount(): number {
  return rtaWorkflows().filter((workflow) => workflow.available).length;
}
