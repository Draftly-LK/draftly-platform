"use client";

import { AlertCircle, Check, CircleCheck, CircleDashed, Eraser, LoaderCircle, PencilLine, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { fieldStatus, printedValue, type FieldStatus } from "@/lib/gazette-forms/field-state";
import { cn } from "@/lib/utils";
import type { ApiFormField } from "@/types/rta";
import { Button } from "@/components/ui/button";

export type FieldDecisionAction = "CONFIRM" | "CORRECT" | "CLEAR";

export interface FieldDecision {
  action: FieldDecisionAction;
  value?: string;
  reason?: string;
}

const STATUS_STYLE: Record<FieldStatus, { icon: typeof CircleCheck; className: string }> = {
  confirmed: { icon: CircleCheck, className: "border-teal bg-teal-bg text-teal" },
  awaiting: { icon: CircleDashed, className: "border-teal bg-teal-bg text-teal" },
  unresolved: { icon: TriangleAlert, className: "border-amber bg-amber-bg text-amber-text" },
};

function Badge({ className, icon: Icon, children }: { className: string; icon: typeof CircleCheck; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex min-h-6 items-center gap-1 rounded-full border px-2 text-xs font-semibold", className)}>
      <Icon className="size-4" strokeWidth={1.5} aria-hidden="true" />
      {children}
    </span>
  );
}

/**
 * Review of one bound form field: the same card in field-by-field review and
 * beside the document. A critical particular is confirmed or cleared, never
 * typed (§9.3, enforced again by the server); CORRECT is offered only where
 * the template allows lawyer-authored text. CLEAR and CORRECT need a reason.
 */
export function FieldReviewCard({
  field,
  caption,
  busy,
  readOnly,
  onDecision,
}: {
  field: ApiFormField;
  /** The printed caption of the blank this field fills, verbatim. */
  caption?: string | null;
  busy: boolean;
  readOnly: boolean;
  onDecision: (decision: FieldDecision) => void;
}) {
  const t = useTranslations("gazette");
  const tRoot = useTranslations();
  const [editing, setEditing] = useState<"CORRECT" | "CLEAR" | null>(null);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");

  const status = fieldStatus(field);
  const printed = printedValue(field);
  const style = STATUS_STYLE[status];
  const canCorrect = field.lawyerAuthoredAllowed && !field.critical;
  const populated = printed !== null;
  const reasonId = `reason-${field.fieldId}`;
  const valueId = `value-${field.fieldId}`;

  const open = (mode: "CORRECT" | "CLEAR") => {
    setEditing(mode);
    setValue(mode === "CORRECT" ? (printed ?? "") : "");
    setReason("");
  };
  const submit = () => {
    if (!editing || !reason.trim()) return;
    onDecision({ action: editing, reason: reason.trim(), ...(editing === "CORRECT" ? { value } : {}) });
    setEditing(null);
  };

  return (
    <article className="space-y-3" data-field-card={field.fieldId}>
      <header>
        <h3 className="font-semibold">{tRoot(field.labelKey)}</h3>
        {caption && <p className="text-muted-ink text-sm">{caption}</p>}
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge className={style.className} icon={style.icon}>
            {t(`status.${status}`)}
          </Badge>
          {field.critical && (
            <Badge className="border-red bg-red-bg text-red" icon={AlertCircle}>
              {t("critical")}
            </Badge>
          )}
          {field.required && (
            <Badge className="border-amber bg-amber-bg text-amber-text" icon={AlertCircle}>
              {t("required")}
            </Badge>
          )}
          {field.aiSuggested && (
            <Badge className="border-teal bg-teal-bg text-teal" icon={CircleDashed}>
              {t("aiSuggested")}
            </Badge>
          )}
        </div>
      </header>

      <div
        className={cn(
          "rounded border p-3 text-sm",
          populated ? "border-border-strong bg-surface" : "border-amber bg-amber-bg text-amber-text",
        )}
      >
        {printed ?? t("unresolvedValue")}
        {!populated && field.unresolvedReason && (
          <div className="mt-1 text-xs">{t(`unresolvedReason.${field.unresolvedReason}`)}</div>
        )}
      </div>

      {field.conflictingCandidates.length > 0 && (
        <div className="border-amber bg-amber-bg rounded border p-3">
          <h4 className="text-amber-text mb-2 text-sm font-semibold">{t("conflicts")}</h4>
          <ul className="space-y-2">
            {field.conflictingCandidates.map((candidate) => (
              <li key={`${candidate.factId}-${candidate.version}`} className="bg-surface rounded p-2 text-sm">
                <div className="font-medium">{String(candidate.value)}</div>
                <div className="text-muted-ink text-xs">
                  {t("candidateStatus", { status: candidate.status })}
                  {candidate.modelReportedConfidence !== null &&
                    ` · ${t("confidence", { value: Math.round(candidate.modelReportedConfidence * 100) })}`}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {field.critical && <p className="text-muted-ink text-xs">{t("criticalNote")}</p>}

      {!readOnly &&
        (editing ? (
          <div className="space-y-2">
            {editing === "CORRECT" && (
              <label className="block text-sm font-medium" htmlFor={valueId}>
                {t("correctedValue")}
                <textarea
                  id={valueId}
                  className="border-border-strong bg-surface mt-1 block w-full rounded border px-3 py-2 font-normal"
                  rows={2}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
              </label>
            )}
            <label className="block text-sm font-medium" htmlFor={reasonId}>
              {t("reason")}
              <input
                id={reasonId}
                className="border-border-strong bg-surface mt-1 block w-full rounded border px-3 py-2 font-normal"
                value={reason}
                placeholder={t("reasonHint")}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                disabled={busy || !reason.trim() || (editing === "CORRECT" && !value.trim())}
                onClick={submit}
              >
                {editing === "CORRECT" ? t("saveCorrection") : t("confirmClear")}
              </Button>
              <Button onClick={() => setEditing(null)}>{t("cancel")}</Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {populated && (
              <Button variant="primary" disabled={busy || status === "confirmed"} onClick={() => onDecision({ action: "CONFIRM" })}>
                {busy ? (
                  <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} aria-hidden="true" />
                ) : (
                  <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />
                )}
                {t("confirm")}
              </Button>
            )}
            {canCorrect && (
              <Button disabled={busy} onClick={() => open("CORRECT")}>
                <PencilLine className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {t("correct")}
              </Button>
            )}
            {populated && (
              <Button disabled={busy} onClick={() => open("CLEAR")}>
                <Eraser className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {t("clear")}
              </Button>
            )}
          </div>
        ))}
    </article>
  );
}
