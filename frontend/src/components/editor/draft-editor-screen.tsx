"use client";

import {
  AlertCircle,
  Check,
  CheckCircle2,
  CircleDashed,
  LoaderCircle,
  Triangle,
  TriangleAlert,
  X,
} from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import {
  getForm,
  markFormStale,
  recordFieldDecision,
  runPreflight,
} from "@/lib/api/drafts";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { useDemoStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ApiFormField, ApiGeneratedForm, ApiPreflightItem } from "@/types/rta";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";

export function DraftEditorScreen({
  matterId,
  draftId,
}: {
  matterId: string;
  draftId: string;
}) {
  return isApiEnabled() ? (
    <ApiBoundDraftEditorScreen matterId={matterId} formId={draftId} />
  ) : (
    <DemoDraftEditorScreen matterId={matterId} draftId={draftId} />
  );
}

function ApiBoundDraftEditorScreen({
  matterId,
  formId,
}: {
  matterId: string;
  formId: string;
}) {
  const getToken = useTokenProvider();
  return <DraftEditorScreenContent matterId={matterId} formId={formId} getToken={getToken} />;
}

function DemoDraftEditorScreen({
  matterId,
  draftId,
}: {
  matterId: string;
  draftId: string;
}) {
  return <DemoDraftEditorContent matterId={matterId} draftId={draftId} />;
}

interface DraftEditorScreenContentProps {
  matterId: string;
  formId: string;
  getToken: TokenProvider;
}

function DraftEditorScreenContent({
  matterId,
  formId,
  getToken,
}: DraftEditorScreenContentProps) {
  const t = useTranslations("draft");
  const tRoot = useTranslations();

  // State
  const [form, setForm] = useState<ApiGeneratedForm | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingFieldId, setProcessingFieldId] = useState<string | null>(null);
  const [runningPreflight, setRunningPreflight] = useState(false);
  const [markingStale, setMarkingStale] = useState(false);
  const [staleReason, setStaleReason] = useState("");

  // Fetch form
  const fetchForm = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getForm(getToken, formId);
      setForm(result);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [getToken, formId, t]);

  useEffect(() => {
    void fetchForm();
  }, [fetchForm]);

  // Handle field decision
  const handleFieldDecision = useCallback(
    async (fieldId: string, action: "CONFIRM" | "CORRECT" | "CLEAR", value?: string) => {
      if (!form) return;
      setProcessingFieldId(fieldId);
      setError(null);
      try {
        const updated = await recordFieldDecision(
          getToken,
          formId,
          { fieldId, action, ...(value !== undefined && { value }) },
          form.version
        );
        setForm(updated);
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 409) {
          setError(t("conflictError"));
        } else {
          setError(cause instanceof ApiError ? cause.message : t("decisionError"));
        }
      } finally {
        setProcessingFieldId(null);
      }
    },
    [form, getToken, formId, t]
  );

  // Handle preflight
  const handleRunPreflight = useCallback(async () => {
    if (!form) return;
    setRunningPreflight(true);
    setError(null);
    try {
      const updated = await runPreflight(getToken, formId);
      setForm(updated);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("preflightError"));
    } finally {
      setRunningPreflight(false);
    }
  }, [form, getToken, formId, t]);

  // Handle mark stale
  const handleMarkStale = useCallback(async () => {
    if (!form) return;
    setMarkingStale(true);
    setError(null);
    try {
      const updated = await markFormStale(
        getToken,
        formId,
        { reason: staleReason || undefined },
        form.version
      );
      setForm(updated);
      setStaleReason("");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setError(t("conflictError"));
      } else {
        setError(cause instanceof ApiError ? cause.message : t("staleError"));
      }
    } finally {
      setMarkingStale(false);
    }
  }, [form, getToken, formId, staleReason, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex items-center gap-2 p-6 text-muted-ink">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          {t("loading")}
        </div>
      </AppShell>
    );
  }

  if (!form) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex gap-3 rounded border border-red bg-red-bg p-6 text-sm text-red">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{t("loadError")}</p>
        </div>
      </AppShell>
    );
  }

  // Group fields by section
  const fieldsBySection = new Map<string, ApiFormField[]>();
  for (const field of form.fields) {
    const section = field.sectionKey;
    if (!fieldsBySection.has(section)) {
      fieldsBySection.set(section, []);
    }
    fieldsBySection.get(section)!.push(field);
  }

  return (
    <AppShell matterId={matterId}>
      <div className="max-w-4xl">
        {/* Header */}
        <header className="border-border bg-surface border-b px-6 py-4">
          <h1 className="text-2xl font-semibold">{tRoot(form.titleKey)}</h1>
          <div className="text-muted-ink mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span>Form {form.formNumber}</span>
            <span>·</span>
            <span>v{form.formVersion}</span>
            <span>·</span>
            <span
              className={cn(
                "inline-flex min-h-6 items-center gap-1 rounded-full border px-2 text-xs font-semibold",
                getFormStateStyles(form.state)
              )}
            >
              {getFormStateIcon(form.state)}
              {tRoot(`generatedFormState.${form.state}`)}
            </span>
          </div>
        </header>

        {/* Watermark banner - always show */}
        <div className="border-amber bg-amber-bg text-amber-text border-b px-6 py-3 font-medium">
          {form.preflight.watermarkKey
            ? tRoot(form.preflight.watermarkKey)
            : "DRAFT — NOT APPROVED FOR EXECUTION OR REGISTRATION"}
        </div>

        {/* Known source defects warning */}
        {form.knownSourceDefectKeys.length > 0 && (
          <div className="border-amber bg-amber-bg text-amber-text border-b px-6 py-4">
            <div className="flex items-start gap-3">
              <Triangle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
              <div>
                <h2 className="font-semibold">Known source text defects</h2>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
                  {form.knownSourceDefectKeys.map((key) => (
                    <li key={key}>{tRoot(key)}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="border-red bg-red-bg text-red mx-6 mt-6 flex gap-3 rounded border p-4 text-sm">
            <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
            <p>{error}</p>
          </div>
        )}

        {/* Fields */}
        <div className="divide-border divide-y border-b">
          {Array.from(fieldsBySection.entries()).map(([sectionKey, fields]) => (
            <section key={sectionKey} className="px-6 py-6">
              <h2 className="mb-6 text-lg font-semibold">{tRoot(sectionKey)}</h2>
              <div className="space-y-8">
                {fields.map((field) => (
                  <FormField
                    key={field.id}
                    field={field}
                    onConfirm={() => void handleFieldDecision(field.fieldId, "CONFIRM")}
                    onCorrect={(value) => void handleFieldDecision(field.fieldId, "CORRECT", value)}
                    onClear={() => void handleFieldDecision(field.fieldId, "CLEAR")}
                    isProcessing={processingFieldId === field.fieldId}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Preflight section */}
        <section className="border-border border-t px-6 py-6">
          <h2 className="mb-4 text-lg font-semibold">Form readiness</h2>

          {/* Preflight status indicators */}
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            <PreflightStatus
              label="Review ready"
              ready={form.preflight.reviewReady}
            />
            <PreflightStatus
              label="Approval ready"
              ready={form.preflight.approvalReady}
            />
            <PreflightStatus
              label="Registration ready"
              ready={false}
              note="Never ready in current templates"
            />
          </div>

          {/* Blocking items */}
          {form.preflight.blocking.length > 0 && (
            <div className="mb-6">
              <h3 className="mb-2 font-semibold text-red">Blocking issues</h3>
              <ul className="space-y-2">
                {form.preflight.blocking.map((item) => (
                  <PreflightItem key={item.code} item={item} />
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {form.preflight.warnings.length > 0 && (
            <div className="mb-6">
              <h3 className="mb-2 font-semibold text-amber-text">Warnings</h3>
              <ul className="space-y-2">
                {form.preflight.warnings.map((item) => (
                  <PreflightItem key={item.code} item={item} />
                ))}
              </ul>
            </div>
          )}

          <div className="flex gap-2">
            <Button onClick={() => void handleRunPreflight()} disabled={runningPreflight}>
              {runningPreflight ? (
                <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
              ) : (
                <Check className="size-4" strokeWidth={1.5} />
              )}
              {runningPreflight ? t("runningPreflight") : t("runPreflight")}
            </Button>
            {form.preflight.approvalReady && (
              <Link href={`/matters/${matterId}/drafts/${form.id}/approval`}>
                <Button variant="primary">
                  <Check className="size-4" strokeWidth={1.5} />
                  Approve
                </Button>
              </Link>
            )}
          </div>
        </section>

        {/* Mark stale section */}
        <section className="border-border border-t px-6 py-6">
          <h2 className="mb-4 text-lg font-semibold">Mark form stale</h2>
          <p className="text-muted-ink mb-4 text-sm">
            Use this if the form&apos;s inputs have moved and need re-evaluation.
          </p>
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Optional reason"
              value={staleReason}
              onChange={(e) => setStaleReason(e.target.value)}
              className="border-border-strong bg-surface flex-1 rounded border px-3 py-2 text-sm"
            />
            <Button onClick={() => void handleMarkStale()} disabled={markingStale}>
              {markingStale ? (
                <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
              ) : (
                <AlertCircle className="size-4" strokeWidth={1.5} />
              )}
              Mark stale
            </Button>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function FormField({
  field,
  onConfirm,
  onCorrect,
  onClear,
  isProcessing,
}: {
  field: ApiFormField;
  onConfirm: () => void;
  onCorrect: (value: string) => void;
  onClear: () => void;
  isProcessing: boolean;
}) {
  const tRoot = useTranslations();
  const [correctionValue, setCorrectionValue] = useState(field.displayValue);
  const [showCorrection, setShowCorrection] = useState(false);

  const isUnresolved = field.displayValue.includes("[[UNRESOLVED:");
  const isConflicted = field.conflictingCandidates.length > 0;

  return (
    <div>
      {/* Label and badges */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{tRoot(field.labelKey)}</h3>
        {field.critical && (
          <span className="inline-flex min-h-6 items-center gap-1 rounded-full border border-red bg-red-bg px-2 text-xs font-semibold text-red">
            <AlertCircle className="size-4" strokeWidth={1.5} aria-hidden="true" />
            Critical
          </span>
        )}
        {field.required && (
          <span className="inline-flex min-h-6 items-center gap-1 rounded-full border border-amber bg-amber-bg px-2 text-xs font-semibold text-amber-text">
            <AlertCircle className="size-4" strokeWidth={1.5} aria-hidden="true" />
            Required
          </span>
        )}
        {field.aiSuggested && (
          <span className="inline-flex min-h-6 items-center gap-1 rounded-full border border-teal bg-teal-bg px-2 text-xs font-semibold text-teal">
            <CircleDashed className="size-4" strokeWidth={1.5} aria-hidden="true" />
            AI-suggested
          </span>
        )}
        {field.awaitingConfirmation && (
          <span className="inline-flex min-h-6 items-center gap-1 rounded-full border border-teal bg-teal-bg px-2 text-xs font-semibold text-teal">
            <CircleDashed className="size-4" strokeWidth={1.5} aria-hidden="true" />
            Awaiting confirmation
          </span>
        )}
      </div>

      {/* Display value or unresolved token */}
      {isUnresolved ? (
        <div className="border-amber bg-amber-bg text-amber-text mb-4 rounded border p-3 font-mono text-sm">
          {field.displayValue}
          {field.unresolvedReason && (
            <div className="text-amber-text/70 mt-1 text-xs">
              {field.unresolvedReason}
            </div>
          )}
        </div>
      ) : (
        <div className="border-border-strong bg-surface mb-4 rounded border p-3 text-sm">
          {field.displayValue}
        </div>
      )}

      {/* Conflicting candidates */}
      {isConflicted && (
        <div className="border-amber bg-amber-bg mb-4 rounded border p-4">
          <h4 className="mb-3 font-semibold text-amber-text">Conflicting candidates</h4>
          <div className="space-y-3">
            {field.conflictingCandidates.map((candidate, idx) => (
              <div key={idx} className="rounded bg-surface p-3 text-sm">
                <div className="font-medium">{String(candidate.value)}</div>
                <div className="text-muted-ink mt-1 text-xs">
                  Status: {candidate.status}
                  {candidate.modelReportedConfidence !== null && (
                    <>
                      {" "}
                      · Confidence: {Math.round(candidate.modelReportedConfidence * 100)}%
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          disabled={isProcessing}
          onClick={onConfirm}
        >
          {isProcessing ? (
            <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
          ) : (
            <Check className="size-4" strokeWidth={1.5} />
          )}
          Confirm
        </Button>

        {field.lawyerAuthoredAllowed && (
          <>
            {showCorrection ? (
              <>
                <input
                  type="text"
                  value={correctionValue}
                  onChange={(e) => setCorrectionValue(e.target.value)}
                  className="border-border-strong bg-surface rounded border px-3 py-2 text-sm"
                  placeholder="Corrected value"
                />
                <Button
                  variant="primary"
                  disabled={isProcessing}
                  onClick={() => {
                    onCorrect(correctionValue);
                    setShowCorrection(false);
                  }}
                >
                  Save
                </Button>
                <Button onClick={() => setShowCorrection(false)}>Cancel</Button>
              </>
            ) : (
              <Button onClick={() => setShowCorrection(true)}>
                Correct
              </Button>
            )}
          </>
        )}

        <Button disabled={isProcessing} onClick={onClear}>
          <X className="size-4" strokeWidth={1.5} />
          Clear
        </Button>
      </div>
    </div>
  );
}

function PreflightStatus({
  label,
  ready,
  note,
}: {
  label: string;
  ready: boolean;
  note?: string;
}) {
  return (
    <div className="border-border-strong bg-surface rounded border p-4">
      <div className="flex items-center gap-2">
        {ready ? (
          <CheckCircle2 className="size-5 text-forest" strokeWidth={1.5} aria-hidden="true" />
        ) : (
          <CircleDashed className="size-5 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
        )}
        <span className="font-semibold">{label}</span>
      </div>
      {note && <div className="text-muted-ink mt-2 text-xs">{note}</div>}
    </div>
  );
}

function PreflightItem({ item }: { item: ApiPreflightItem }) {
  const tRoot = useTranslations();
  return (
    <div className="flex gap-3 rounded border border-amber bg-amber-bg/50 p-3 text-sm">
      <TriangleAlert
        className="mt-0.5 size-4 shrink-0 text-amber-text"
        strokeWidth={1.5}
        aria-hidden="true"
      />
      <div>
        <div className="font-semibold">{item.code}</div>
        <div className="text-muted-ink mt-1">{tRoot(item.explanationKey)}</div>
      </div>
    </div>
  );
}

function getFormStateStyles(state: string): string {
  switch (state) {
    case "GENERATED_DRAFT":
      return "border-border-strong bg-surface text-ink";
    case "UNRESOLVED":
      return "border-amber bg-amber-bg text-amber-text";
    case "REVIEW_READY":
      return "border-teal bg-teal-bg text-teal";
    case "APPROVED":
      return "border-forest bg-soft-green text-forest";
    default:
      return "border-border-strong bg-surface text-ink";
  }
}

function getFormStateIcon(state: string) {
  switch (state) {
    case "GENERATED_DRAFT":
      return <CircleDashed className="size-4" strokeWidth={1.5} aria-hidden="true" />;
    case "APPROVED":
      return <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />;
    case "UNRESOLVED":
      return <AlertCircle className="size-4" strokeWidth={1.5} aria-hidden="true" />;
    default:
      return <CircleDashed className="size-4" strokeWidth={1.5} aria-hidden="true" />;
  }
}

function DemoDraftEditorContent({
  matterId,
  draftId,
}: {
  matterId: string;
  draftId: string;
}) {
  const t = useTranslations("draft");
  const allDrafts = useDemoStore((state) => state.drafts);
  const draft = allDrafts.find((item) => item.id === draftId);

  if (!draft) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex gap-3 rounded border border-red bg-red-bg p-6 text-sm text-red">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>Draft not found</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell matterId={matterId}>
      <div className="max-w-4xl rounded border border-border-strong bg-surface p-6">
        <h1 className="text-2xl font-semibold">{draft.title}</h1>
        <p className="text-muted-ink mt-2">{t("noDrafts")}</p>
      </div>
    </AppShell>
  );
}
