import type { FormTemplate, FormTemplateField, VerifiedFact } from "@/types";

/**
 * A fact may only reach a draft once a lawyer has confirmed or corrected it.
 * This is the single source of truth for that rule: the drafting gate, the
 * pre-flight checklist, and the editor's FactChip all derive from it.
 */
export function isFactUsable(fact: Pick<VerifiedFact, "verificationState">): boolean {
  return fact.verificationState === "verified" || fact.verificationState === "corrected";
}

export type FieldReadinessStatus =
  | "satisfied"
  | "unreviewed"
  | "conflict"
  | "blocked"
  | "missing";

export interface FieldReadiness {
  field: FormTemplateField;
  fact?: VerifiedFact;
  status: FieldReadinessStatus;
}

export interface TemplateReadiness {
  fields: FieldReadiness[];
  requiredTotal: number;
  requiredSatisfied: number;
  /** Required fields that are not yet satisfied — what the lawyer must resolve. */
  outstanding: FieldReadiness[];
  canGenerate: boolean;
}

function statusFor(fact: VerifiedFact | undefined): FieldReadinessStatus {
  if (!fact) return "missing";
  if (isFactUsable(fact)) return "satisfied";
  if (fact.verificationState === "conflict") return "conflict";
  if (fact.verificationState === "blocked") return "blocked";
  return "unreviewed";
}

/**
 * Answers "what does this form still need?" by matching each template field to
 * the matter's facts. `factBinding` holds a fact *key* rather than an id so the
 * binding survives `createMatter`, which clones facts under prefixed ids.
 */
export function deriveTemplateReadiness(
  template: FormTemplate,
  facts: VerifiedFact[],
): TemplateReadiness {
  const byKey = new Map(facts.map((fact) => [fact.key, fact]));

  const fields: FieldReadiness[] = [...template.fields]
    .sort((a, b) => a.order - b.order)
    .map((field) => {
      const fact = field.factBinding ? byKey.get(field.factBinding) : undefined;
      return { field, fact, status: statusFor(fact) };
    });

  const required = fields.filter((entry) => entry.field.required);
  const outstanding = required.filter((entry) => entry.status !== "satisfied");

  return {
    fields,
    requiredTotal: required.length,
    requiredSatisfied: required.length - outstanding.length,
    outstanding,
    canGenerate: outstanding.length === 0,
  };
}
