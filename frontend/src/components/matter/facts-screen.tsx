"use client";

import { AlertCircle, CheckCircle, FileText, LoaderCircle, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ApiError, isApiEnabled } from "@/lib/api/client";
import { listForms, getForm } from "@/lib/api/drafts";
import { listCheckResults } from "@/lib/api/checks";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import type { ApiFormField, ApiCheckResult, ApiFactCandidate } from "@/types/rta";

/** Shared prop type for a translator passed down to a child component. */
type Translator = ReturnType<typeof useTranslations>;

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
  const [fields, setFields] = useState<ApiFormField[]>([]);
  const [checkResults, setCheckResults] = useState<ApiCheckResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          const form = await getForm(getToken, firstForm.id);
          if (!cancelled) {
            setFields(form.fields);
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

  // Filter to only fields with facts
  const factsFields = fields.filter((field) => field.factId !== null);

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

        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[1200px] border-collapse text-sm">
            <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs font-semibold uppercase">
              <tr className="border-border h-10 border-b">
                <th className="px-3 text-left">{t("fact")}</th>
                <th className="px-3 text-left">{t("value")}</th>
                <th className="px-3 text-left">{t("source")}</th>
                <th className="px-3 text-left">Version</th>
                <th className="px-3 text-left">Status</th>
                <th className="px-3 text-left">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-border divide-y">
              {factsFields.map((field) => (
                <FactRow
                  key={field.id}
                  field={field}
                  checks={factToChecks.get(field.factId!) || []}
                  t={t}
                  tRoot={tRoot}
                />
              ))}
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
}: {
  field: ApiFormField;
  checks: ApiCheckResult[];
  t: Translator;
  tRoot: Translator;
}) {
  return (
    <tr className="border-border h-11 hover:bg-hover-bg">
      <td className="px-3 font-medium">{tRoot(field.labelKey)}</td>
      <td className="px-3 max-w-64 truncate text-sm">{field.displayValue}</td>
      <td className="px-3 text-sm">
        <span className="text-muted-ink">Form {field.sectionKey}</span>
      </td>
      <td className="px-3 text-sm">{field.factVersion ?? "—"}</td>
      <td className="px-3">
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
      <td className="px-3">
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
