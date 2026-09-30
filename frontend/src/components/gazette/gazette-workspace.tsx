"use client";

import { ChevronLeft, ChevronRight, FileText, ListChecks, Lock, SkipForward } from "lucide-react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { listSlots, type GazetteForm, type SlotInfo } from "@/lib/gazette-forms";
import { countFilled, printedValue, type SlotValues } from "@/lib/gazette-forms/field-state";
import { loadSlotValues, saveSlotValues } from "@/lib/gazette-forms/slot-storage";
import { cn } from "@/lib/utils";
import type { ApiFormField, ApiGeneratedForm } from "@/types/rta";
import { Button } from "@/components/ui/button";
import { FieldReviewCard, type FieldDecision } from "./field-review-card";
import { GazetteContext, type GazetteContextValue } from "./gazette-context";
import { useSlotLabel } from "./slot-label";

const GazetteDocument = dynamic(() => import("./gazette-document"), { ssr: false });

export type DraftingMode = "guided" | "document";

/** A step in field-by-field review: a blank on the page, or a field the page has no blank for. */
type Step = { kind: "slot"; slot: SlotInfo } | { kind: "field"; field: ApiFormField };

const FIELD_STEP = "field:";

function stepId(step: Step): string {
  return step.kind === "slot" ? step.slot.id : FIELD_STEP + step.field.fieldId;
}

/**
 * The gazette drafting workspace. Two ways to fill the same form:
 *
 * - **Field by field** walks every blank in printed order, then any bound
 *   field the printed page has no blank for.
 * - **Fill in document** puts the lawyer on the page itself.
 *
 * Both read and write one set of values, so switching modes loses nothing.
 * Bound fields go through the draft API's field decisions; free blanks are
 * kept per form on this device until the API can store them.
 */
export function GazetteWorkspace({
  form,
  gazette,
  busyFieldId,
  onDecision,
}: {
  form: ApiGeneratedForm;
  gazette: GazetteForm;
  busyFieldId: string | null;
  onDecision: (fieldId: string, decision: FieldDecision) => void;
}) {
  const t = useTranslations("gazette");
  const label = useSlotLabel();
  const readOnly = form.approvalId !== null || form.state === "APPROVED";

  const slots = useMemo(() => listSlots(gazette.document), [gazette.document]);
  const slotById = useMemo(() => Object.fromEntries(slots.map((slot) => [slot.id, slot])), [slots]);
  const fields = useMemo(
    () => Object.fromEntries(form.fields.map((field) => [field.fieldId, field])),
    [form.fields],
  );
  const steps = useMemo<Step[]>(() => {
    const placed = new Set(slots.map((slot) => slot.field).filter(Boolean));
    const unplaced = [...form.fields]
      .sort((a, b) => a.order - b.order)
      .filter((field) => !placed.has(field.fieldId));
    return [
      ...slots.map((slot) => ({ kind: "slot" as const, slot })),
      ...unplaced.map((field) => ({ kind: "field" as const, field })),
    ];
  }, [slots, form.fields]);
  const unplacedFields = steps.flatMap((step) => (step.kind === "field" ? [step.field] : []));

  const [mode, setMode] = useState<DraftingMode>("guided");
  const [values, setValues] = useState<SlotValues>({});
  const [loaded, setLoaded] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(steps[0] ? stepId(steps[0]) : null);

  // Storage is per device and read after mount, so server and first client
  // render agree.
  useEffect(() => {
    setValues(loadSlotValues(form.id));
    setLoaded(true);
  }, [form.id]);
  useEffect(() => {
    if (loaded) saveSlotValues(form.id, values);
  }, [form.id, values, loaded]);

  const setValue = useCallback((slotId: string, value: string) => {
    setValues((current) => ({ ...current, [slotId]: value }));
  }, []);

  const activate = useCallback((id: string) => setActiveId(id), []);

  const context = useMemo<GazetteContextValue>(
    () => ({ values, setValue, fields, slots: slotById, activeSlotId: activeId, activate, readOnly }),
    [values, setValue, fields, slotById, activeId, activate, readOnly],
  );

  const index = Math.max(0, steps.findIndex((step) => stepId(step) === activeId));
  const step = steps[index];
  const isStepFilled = useCallback(
    (candidate: Step) => {
      if (candidate.kind === "field") return printedValue(candidate.field) !== null;
      if (candidate.slot.field) {
        const field = fields[candidate.slot.field];
        return field ? printedValue(field) !== null : false;
      }
      return (values[candidate.slot.id] ?? "").trim().length > 0;
    },
    [fields, values],
  );
  const filled = countFilled(slots, fields, values);

  const goTo = (target: number) => {
    const next = steps[Math.min(steps.length - 1, Math.max(0, target))];
    if (next) setActiveId(stepId(next));
  };
  const nextEmpty = () => {
    for (let offset = 1; offset <= steps.length; offset += 1) {
      const candidate = steps[(index + offset) % steps.length];
      if (candidate && !isStepFilled(candidate)) {
        setActiveId(stepId(candidate));
        return;
      }
    }
  };

  // Keep the step being reviewed in view on the page.
  useEffect(() => {
    if (!activeId || activeId.startsWith(FIELD_STEP)) return;
    const target = document.querySelector(`[data-gz-slot="${CSS.escape(activeId)}"]`);
    if (target instanceof HTMLElement && mode === "guided") {
      target.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [activeId, mode]);

  const renderStep = (current: Step) => {
    if (current.kind === "field" || current.slot.field) {
      const field = current.kind === "field" ? current.field : fields[current.slot.field!];
      if (!field) {
        return <p className="text-muted-ink text-sm">{t("fieldMissing")}</p>;
      }
      return (
        <FieldReviewCard
          key={field.fieldId}
          field={field}
          caption={current.kind === "slot" ? label(current.slot) : null}
          busy={busyFieldId === field.fieldId}
          readOnly={readOnly}
          onDecision={(decision) => onDecision(field.fieldId, decision)}
        />
      );
    }
    const slot = current.slot;
    const inputId = `panel-${slot.id}`;
    const common = {
      id: inputId,
      value: values[slot.id] ?? "",
      readOnly,
      className: "border-border-strong bg-surface mt-1 block w-full rounded border px-3 py-2 font-normal",
      onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setValue(slot.id, event.target.value),
    };
    return (
      <div className="space-y-2" data-slot-card={slot.id}>
        <label className="block font-semibold" htmlFor={inputId}>
          {label(slot)}
          {slot.multiline ? <textarea rows={4} {...common} /> : <input type="text" {...common} />}
        </label>
        <p className="text-muted-ink text-xs">{t("localOnly")}</p>
      </div>
    );
  };

  return (
    <GazetteContext.Provider value={context}>
      <div className="border-border bg-surface flex flex-wrap items-center gap-3 border-b px-6 py-3">
        <div role="group" aria-label={t("modeLabel")} className="border-border-strong inline-flex rounded border p-0.5">
          {(["guided", "document"] as const).map((candidate) => {
            const Icon = candidate === "guided" ? ListChecks : FileText;
            return (
              <button
                key={candidate}
                type="button"
                aria-pressed={mode === candidate}
                className={cn(
                  "inline-flex min-h-9 items-center gap-2 rounded px-3 text-sm font-medium",
                  mode === candidate ? "bg-selected-bg text-forest" : "hover:bg-hover-bg",
                )}
                onClick={() => setMode(candidate)}
              >
                <Icon className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {t(candidate === "guided" ? "modeGuided" : "modeDocument")}
              </button>
            );
          })}
        </div>
        <p className="text-muted-ink text-sm tabular-nums" aria-live="polite">
          {t("progress", { filled, total: slots.length })}
        </p>
        <p className="text-muted-ink ml-auto inline-flex items-center gap-1 text-xs">
          <Lock className="size-4" strokeWidth={1.5} aria-hidden="true" />
          {t("lockedNote")}
        </p>
      </div>

      <div className="grid min-[1100px]:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="border-border bg-surface border-b p-5 min-[1100px]:sticky min-[1100px]:top-0 min-[1100px]:max-h-screen min-[1100px]:overflow-y-auto min-[1100px]:border-b-0 min-[1100px]:border-r">
          {mode === "guided" && step ? (
            <div className="space-y-4">
              <p className="text-muted-ink text-sm tabular-nums">
                {t("step", { current: index + 1, total: steps.length })}
                {step.kind === "field" && ` · ${t("notOnForm")}`}
              </p>
              {renderStep(step)}
              <div className="flex flex-wrap gap-2 pt-2">
                <Button disabled={index === 0} onClick={() => goTo(index - 1)}>
                  <ChevronLeft className="size-4" strokeWidth={1.5} aria-hidden="true" />
                  {t("previous")}
                </Button>
                <Button variant="primary" disabled={index >= steps.length - 1} onClick={() => goTo(index + 1)}>
                  {t("next")}
                  <ChevronRight className="size-4" strokeWidth={1.5} aria-hidden="true" />
                </Button>
                <Button variant="ghost" onClick={nextEmpty}>
                  <SkipForward className="size-4" strokeWidth={1.5} aria-hidden="true" />
                  {t("nextEmpty")}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {step ? (
                renderStep(step)
              ) : (
                <p className="text-muted-ink text-sm">{t("selectBlank")}</p>
              )}
              {unplacedFields.length > 0 && (
                <section>
                  <h3 className="font-semibold">{t("notOnForm")}</h3>
                  <p className="text-muted-ink mt-1 text-xs">{t("notOnFormBody")}</p>
                  <ul className="mt-2 space-y-1">
                    {unplacedFields.map((field) => (
                      <li key={field.fieldId}>
                        <UnplacedFieldButton
                          field={field}
                          active={activeId === FIELD_STEP + field.fieldId}
                          onSelect={() => activate(FIELD_STEP + field.fieldId)}
                        />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </aside>
        <section className="bg-canvas min-w-0 p-4 sm:p-6">
          <p className="text-muted-ink mx-auto mb-3 max-w-[922px] text-xs">
            {t("sourceBody", { form: gazette.formNumber, pages: gazette.pages.length })}
          </p>
          <div
            data-print-surface
            className="border-border-strong mx-auto max-w-[922px] border"
            style={{ "--gz-font": "13px" } as React.CSSProperties}
          >
            <GazetteDocument document={gazette.document} />
          </div>
        </section>
      </div>
    </GazetteContext.Provider>
  );
}

function UnplacedFieldButton({ field, active, onSelect }: { field: ApiFormField; active: boolean; onSelect: () => void }) {
  const tRoot = useTranslations();
  const t = useTranslations("gazette");
  const value = printedValue(field);
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "border-border w-full rounded border px-3 py-2 text-left text-sm",
        active ? "bg-selected-bg" : "hover:bg-hover-bg",
      )}
      onClick={onSelect}
    >
      <span className="block font-medium">{tRoot(field.labelKey)}</span>
      <span className="text-muted-ink block text-xs">{value ?? t("status.unresolved")}</span>
    </button>
  );
}
