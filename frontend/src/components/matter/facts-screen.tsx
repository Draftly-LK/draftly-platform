"use client";

import { AlertCircle, Check, CheckCircle, FileText, LoaderCircle, AlertTriangle, X } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, isApiEnabled } from "@/lib/api/client";
import { listForms, getForm, recordFieldDecision } from "@/lib/api/drafts";
import { listCheckResults } from "@/lib/api/checks";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import type { ApiFormField, ApiGeneratedForm, ApiCheckResult, ApiFactCandidate } from "@/types/rta";

/** Shared prop type for a translator passed down to a child component. */
type Translator = ReturnType<typeof useTranslations>;

type FactFilter = "all" | "unreviewed" | "lowConfidence" | "conflicting" | "missing";

const LOW_CONFIDENCE_THRESHOLD = 0.7;

function matchesFilter(field: ApiFormField, filter: FactFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "unreviewed":
      return field.awaitingConfirmation && field.reviewDecisionId === null;
    case "conflicting":
      return field.conflictingCandidates.length > 0;
    case "missing":
      return field.unresolvedReason !== null;
    case "lowConfidence":
      return field.conflictingCandidates.some(
        (candidate) =>
          candidate.modelReportedConfidence !== null &&
          candidate.modelReportedConfidence < LOW_CONFIDENCE_THRESHOLD,
      );
  }
}

export function FactsScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundFactsScreen matterId={matterId} />
  ) : (
    <OfflineFactsScreen matterId={matterId} />
  );
}

function ApiBoundFactsScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  const t = useTranslations("facts");
  const tRoot = useTranslations();
  const [form, setForm] = useState<ApiGeneratedForm | null>(null);
  const [checkResults, setCheckResults] = useState<ApiCheckResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingFieldId, setProcessingFieldId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FactFilter>("all");

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        // Fetch forms
        const formsResult = await listForms(getToken, matterId);
        const firstForm = formsResult.items[0];
        if (firstForm) {
          // Get the most recent form
          const loadedForm = await getForm(getToken, firstForm.id);
          if (!cancelled) {
            setForm(loadedForm);
          }
        }

        // Fetch check results
        const checksResult = await listCheckResults(getToken, matterId);
        if (!cancelled) {
          setCheckResults(checksResult.items);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof ApiError ? cause.message : t("error"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchData();
    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, t]);

  const handleFieldDecision = useCallback(
    async (fieldId: string, action: "CONFIRM" | "CORRECT" | "CLEAR", value?: string) => {
      if (!form) return;
      setProcessingFieldId(fieldId);
      setError(null);
      try {
        const updated = await recordFieldDecision(
          getToken,
          form.id,
          { fieldId, action, ...(value !== undefined && { value }) },
          form.version,
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
    [form, getToken, t],
  );

  // Filter to only fields with facts
  const factsFields = useMemo(
    () => (form?.fields ?? []).filter((field) => field.factId !== null),
    [form],
  );
  const visibleFields = useMemo(
    () => factsFields.filter((field) => matchesFilter(field, filter)),
    [factsFields, filter],
  );

  // Build a map of factId -> checks that reference it
  const factToChecks = new Map<string, ApiCheckResult[]>();
  checkResults.forEach((check) => {
    check.inputFactVersions.forEach((factPin) => {
      if (!factToChecks.has(factPin.factId)) {
        factToChecks.set(factPin.factId, []);
      }
      factToChecks.get(factPin.factId)!.push(check);
    });
  });

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="flex items-center justify-center gap-2 p-12">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          <span>{t("loading")}</span>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="border-red bg-red-bg text-red m-6 flex gap-3 rounded border p-4">
          <AlertCircle className="size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <span>{error}</span>
        </div>
      </AppShell>
    );
  }

  if (factsFields.length === 0) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="p-6">
          <div className="border-border-strong bg-surface rounded border p-6 text-center">
            <FileText className="mx-auto size-12 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
            <h2 className="mt-4 text-lg font-semibold">{t("noFormsEmpty")}</h2>
            <p className="text-muted-ink mt-2">{t("noFormsEmptyBody")}</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link
                href={`/matters/${matterId}/drafts`}
                className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
              >
                {t("generateFormLink")}
              </Link>
              <Link
                href={`/matters/${matterId}/checks`}
                className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
              >
                {t("runChecksLink")}
              </Link>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border-strong bg-selected-bg rounded border p-4 text-sm">
          <div className="flex gap-2">
            <InfoIcon />
            <div>
              <p className="font-medium">{t("derivedTitle")}</p>
              <p className="text-muted-ink mt-1">{t("derivedBody")}</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="border-red bg-red-bg text-red mt-4 flex gap-3 rounded border p-4 text-sm">
            <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <span className="text-muted-ink text-xs font-semibold uppercase">{t("filterLabel")}:</span>
          {(["all", "unreviewed", "lowConfidence", "conflicting", "missing"] as FactFilter[]).map(
            (option) => (
              <button
                key={option}
                type="button"
                onClick={() => setFilter(option)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                  filter === option
                    ? "border-forest bg-soft-green text-forest"
                    : "border-border-strong bg-surface text-muted-ink hover:bg-hover-bg"
                }`}
              >
                {t(option === "all" ? "all" : option === "unreviewed" ? "unreviewedFilter" : option)}
              </button>
            ),
          )}
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[1400px] border-collapse text-sm">
            <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs font-semibold uppercase">
              <tr className="border-border h-10 border-b">
                <th className="px-3 text-left">{t("fact")}</th>
                <th className="px-3 text-left">{t("value")}</th>
                <th className="px-3 text-left">{t("source")}</th>
                <th className="px-3 text-left">Version</th>
                <th className="px-3 text-left">Status</th>
                <th className="px-3 text-left">Evidence</th>
                <th className="px-3 text-left">{t("actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-border divide-y">
              {visibleFields.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-muted-ink px-3 py-6 text-center">
                    {t("noMatchingFilter")}
                  </td>
                </tr>
              ) : (
                visibleFields.map((field) => (
                  <FactRow
                    key={field.id}
                    field={field}
                    checks={factToChecks.get(field.factId!) || []}
                    t={t}
                    tRoot={tRoot}
                    isProcessing={processingFieldId === field.fieldId}
                    onConfirm={() => void handleFieldDecision(field.fieldId, "CONFIRM")}
                    onCorrect={(value) => void handleFieldDecision(field.fieldId, "CORRECT", value)}
                    onClear={() => void handleFieldDecision(field.fieldId, "CLEAR")}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}

function FactRow({
  field,
  checks,
  t,
  tRoot,
  isProcessing,
  onConfirm,
  onCorrect,
  onClear,
}: {
  field: ApiFormField;
  checks: ApiCheckResult[];
  t: Translator;
  tRoot: Translator;
  isProcessing: boolean;
  onConfirm: () => void;
  onCorrect: (value: string) => void;
  onClear: () => void;
}) {
  const [showCorrection, setShowCorrection] = useState(false);
  const [correctionValue, setCorrectionValue] = useState(field.displayValue);

  return (
    <tr className="border-border hover:bg-hover-bg align-top">
      <td className="px-3 py-2 font-medium">{tRoot(field.labelKey)}</td>
      <td className="px-3 py-2 max-w-64 truncate text-sm">{field.displayValue}</td>
      <td className="px-3 py-2 text-sm">
        <span className="text-muted-ink">Form {field.sectionKey}</span>
      </td>
      <td className="px-3 py-2 text-sm">{field.factVersion ?? "—"}</td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          {field.aiSuggested && (
            <StatusBadge icon="info" label={t("aiSuggested")} />
          )}
          {field.awaitingConfirmation && (
            <StatusBadge icon="warning" label={t("awaitingConfirmation")} />
          )}
          {field.reviewedBy && (
            <span className="text-muted-ink text-xs">Reviewed by: {field.reviewedBy}</span>
          )}
        </div>
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-col gap-1 text-xs text-muted-ink">
          {field.evidenceReferenceIds.length > 0 && (
            <span>Evidence references: {field.evidenceReferenceIds.length}</span>
          )}
          {checks.length > 0 && (
            <span>Referenced by {checks.length} check(s)</span>
          )}
          {field.conflictingCandidates.length > 0 && (
            <ConflictIndicator candidates={field.conflictingCandidates} t={t} />
          )}
        </div>
      </td>
      <td className="px-3 py-2">
        {showCorrection ? (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              value={correctionValue}
              onChange={(event) => setCorrectionValue(event.target.value)}
              className="border-border-strong bg-surface rounded border px-2 py-1 text-sm"
            />
            <div className="flex gap-2">
              <Button
                variant="primary"
                disabled={isProcessing}
                onClick={() => {
                  onCorrect(correctionValue);
                  setShowCorrection(false);
                }}
              >
                {t("saveCorrection")}
              </Button>
              <Button onClick={() => setShowCorrection(false)}>{t("cancel")}</Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={isProcessing} onClick={onConfirm}>
              {isProcessing ? (
                <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
              ) : (
                <Check className="size-4" strokeWidth={1.5} />
              )}
              {t("confirm")}
            </Button>
            {field.lawyerAuthoredAllowed && (
              <Button disabled={isProcessing} onClick={() => setShowCorrection(true)}>
                {t("correct")}
              </Button>
            )}
            <Button disabled={isProcessing} onClick={onClear}>
              <X className="size-4" strokeWidth={1.5} />
              {t("clearValue")}
            </Button>
          </div>
        )}
      </td>
    </tr>
  );
}

function ConflictIndicator({
  candidates,
  t,
}: {
  candidates: ApiFactCandidate[];
  t: Translator;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded border border-amber bg-amber-bg/50 p-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-amber-text font-medium"
      >
        <AlertTriangle className="size-4" strokeWidth={1.5} aria-hidden="true" />
        {t("conflictingCandidates")}
      </button>
      {open && (
        <div className="mt-2 space-y-2 border-t border-amber pt-2">
          {candidates.map((candidate, index) => (
            <div key={index} className="text-xs">
              <div className="font-medium">Candidate {index + 1}</div>
              <div className="text-amber-text text-xs">
                {String(candidate.value)}
              </div>
              <div className="text-muted-ink mt-1 text-xs">
                {t("candidateStatus")}: {candidate.status}
                {candidate.modelReportedConfidence !== null && (
                  <span>
                    · {t("candidateConfidence")}: {Math.round(
                      candidate.modelReportedConfidence * 100
                    )}
                    %
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({
  icon,
  label,
}: {
  icon: "info" | "warning";
  label: string;
}) {
  const Icon = icon === "info" ? CheckCircle : AlertTriangle;
  const colorClass =
    icon === "info"
      ? "border-forest text-forest"
      : "border-amber text-amber-text";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${colorClass}`}
    >
      <Icon className="size-3" strokeWidth={1.5} aria-hidden="true" />
      {label}
    </span>
  );
}

function InfoIcon() {
  return (
    <div className="mt-1 shrink-0">
      <AlertCircle
        className="size-5 text-forest"
        strokeWidth={1.5}
        aria-hidden="true"
      />
    </div>
  );
}

function OfflineFactsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("facts");

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border-strong bg-surface rounded border p-6 text-center">
          <FileText className="mx-auto size-12 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold">{t("noFormsEmpty")}</h2>
          <p className="text-muted-ink mt-2">{t("noFormsEmptyBody")}</p>
        </div>
      </div>
    </AppShell>
  );
}
