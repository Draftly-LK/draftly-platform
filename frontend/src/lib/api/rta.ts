/**
 * RTA rule-pack API calls (read-only).
 *
 * Mirrors backend/src/modules/content_governance/api/router.py. The rule pack
 * has no write surface: governed content changes through a reviewed code change
 * plus counsel approval (§13.2.9), never through an endpoint.
 *
 * The frontend also ships a generated copy of the taxonomy
 * (`src/lib/rta/taxonomy.generated.json`) so New Matter can render before there
 * is a matter to ask about. These functions read the *live* rule pack, which is
 * what a screen should use when it must not be a build behind the server.
 */

import { apiFetch, type TokenProvider } from "@/lib/api/client";
import type { AnswerValueKind, QuestionStage, RtaTaxonomyContract } from "@/types/rta";

/** One selectable value. `value` is the stored answer, never the label. */
export interface ApiRtaQuestionOption {
  value: string;
  labelKey: string;
}

/** Mirrors one entry of `questions_contract()` in rule_pack_export.py. */
export interface ApiRtaQuestion {
  id: string;
  stage: QuestionStage;
  order: number;
  promptKey: string;
  whyKey: string;
  valueKind: AnswerValueKind;
  options: ApiRtaQuestionOption[];
  activatesModuleIds: string[];
  /** Only set for questions that appear on a trigger rather than always (§4.3). */
  triggerNoteKey: string | null;
  /** A model may *propose* a value. Never weakens `lawyerConfirmationRequired`. */
  inferable: boolean;
  lawyerConfirmationRequired: boolean;
  controlsV0Eligibility: boolean;
  v0Required: boolean;
  /** False only where "unknown" is not a meaningful answer (upload, attestation). */
  allowsUnknown: boolean;
}

/** Mirrors `questions_contract()`. */
export interface ApiRtaQuestionsContract {
  version: string;
  questions: ApiRtaQuestion[];
}

/** Families, the 22 prescribed instruments, processes, services, and modules. */
export function getRtaTaxonomy(getToken: TokenProvider): Promise<RtaTaxonomyContract> {
  return apiFetch<RtaTaxonomyContract>("/api/v1/rta/taxonomy", { getToken });
}

/** Intake question definitions for the routing and resolution interviews. */
export function getRtaQuestions(getToken: TokenProvider): Promise<ApiRtaQuestionsContract> {
  return apiFetch<ApiRtaQuestionsContract>("/api/v1/rta/questions", { getToken });
}
