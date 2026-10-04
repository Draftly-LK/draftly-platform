"use client";

import {
  AlertCircle,
  Check,
  CheckCircle2,
  CircleDashed,
  LoaderCircle,
  Triangle,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiErrorMessage, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { getForm, markFormStale, recordFieldDecision, runPreflight } from "@/lib/api/drafts";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { gazetteFormFor } from "@/lib/gazette-forms";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import { applyDemoDecision, DemoDecisionRefused, demoGazetteForm } from "@/lib/gazette-forms/demo-forms";
import { useDemoStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ApiFormField, ApiGeneratedForm, ApiPreflightItem } from "@/types/rta";
import { FieldReviewCard, type FieldDecision } from "@/components/gazette/field-review-card";
import { GazetteWorkspace } from "@/components/gazette/gazette-workspace";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";

type DecisionBody = FieldDecision & { fieldId: string };

/** Where the form comes from: the draft API, or the offline synthetic demo. */
interface FormSource {
  load: () => Promise<ApiGeneratedForm>;
  decide: (form: ApiGeneratedForm, body: DecisionBody) => Promise<ApiGeneratedForm>;
  preflight: (form: ApiGeneratedForm) => Promise<ApiGeneratedForm>;
  markStale: (form: ApiGeneratedForm, reason: string | undefined) => Promise<ApiGeneratedForm>;
}

export function DraftEditorScreen({ matterId, draftId }: { matterId: string; draftId: string }) {
  return isApiEnabled() ? (
    <ApiBoundDraftEditorScreen matterId={matterId} formId={draftId} />
  ) : (
    <DemoDraftEditorScreen matterId={matterId} draftId={draftId} />
  );
}

function ApiBoundDraftEditorScreen({ matterId, formId }: { matterId: string; formId: string }) {
  const getToken = useTokenProvider();
  const source = useMemo(() => apiSource(getToken, formId), [getToken, formId]);
  return <DraftEditorScreenContent matterId={matterId} source={source} />;
}

function apiSource(getToken: TokenProvider, formId: string): FormSource {
  return {
    load: () => getForm(getToken, formId),
    decide: (form, body) => recordFieldDecision(getToken, formId, body, form.version),
    preflight: () => runPreflight(getToken, formId),
    markStale: (form, reason) => markFormStale(getToken, formId, { reason }, form.version),
  };
}

/** Offline demo: the synthetic gazette forms, decided locally by the API's rules. */
function demoSource(seed: ApiGeneratedForm): FormSource {
  return {
    load: async () => seed,
    decide: async (form, body) => applyDemoDecision(form, body),
    preflight: async (form) => form,
    markStale: async (form, reason) => ({ ...form, staleReason: reason ?? "", state: "STALE_TEMPLATE" }),
  };
}

function DemoDraftEditorScreen({ matterId, draftId }: { matterId: string; draftId: string }) {
  const seed = useMemo(() => demoGazetteForm(draftId), [draftId]);
  const source = useMemo(() => (seed ? demoSource(seed) : null), [seed]);
  if (source) return <DraftEditorScreenContent matterId={matterId} source={source} />;
  return <LegacyDemoDraft matterId={matterId} draftId={draftId} />;
}

function DraftEditorScreenContent({ matterId, source }: { matterId: string; source: FormSource }) {
  const t = useTranslations("draft");
  const tGazette = useTranslations("gazette");
  const tRoot = useTranslations();

  const [form, setForm] = useState<ApiGeneratedForm | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingFieldId, setProcessingFieldId] = useState<string | null>(null);
  const [runningPreflight, setRunningPreflight] = useState(false);
  const [markingStale, setMarkingStale] = useState(false);
  const [staleReason, setStaleReason] = useState("");

  const describe = useCallback(
    (cause: unknown, fallback: string) => {
      if (cause instanceof DemoDecisionRefused) return tGazette(`refused.${cause.code}`);
      if (cause instanceof ApiError && cause.status === 409) return t("conflictError");
      if (cause instanceof ApiError) return apiErrorMessage(cause, fallback);
      return fallback;
    },
    [t, tGazette],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    source
      .load()
      .then((result) => {
        if (!cancelled) setForm(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describe(cause, t("loadError")));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [source, describe, t]);

  const handleFieldDecision = useCallback(
    async (fieldId: string, decision: FieldDecision) => {
      if (!form) return;
      setProcessingFieldId(fieldId);
      setError(null);
      try {
        setForm(await source.decide(form, { fieldId, ...decision }));
      } catch (cause) {
        setError(describe(cause, t("decisionError")));
      } finally {
        setProcessingFieldId(null);
      }
    },
    [form, source, describe, t],
  );

  const handleRunPreflight = useCallback(async () => {
    if (!form) return;
    setRunningPreflight(true);
    setError(null);
    try {
      setForm(await source.preflight(form));
    } catch (cause) {
      setError(describe(cause, t("preflightError")));
    } finally {
      setRunningPreflight(false);
    }
  }, [form, source, describe, t]);

  const handleMarkStale = useCallback(async () => {
    if (!form) return;
    setMarkingStale(true);
    setError(null);
    try {
      setForm(await source.markStale(form, staleReason || undefined));
      setStaleReason("");
    } catch (cause) {
      setError(describe(cause, t("staleError")));
    } finally {
      setMarkingStale(false);
    }
  }, [form, source, staleReason, describe, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <div className="text-muted-ink flex items-center gap-2 p-6">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          {t("loading")}
        </div>
      </AppShell>
    );
  }

  if (!form) {
    return (
      <AppShell matterId={matterId}>
        <div className="border-red bg-red-bg text-red m-6 flex gap-3 rounded border p-6 text-sm">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{error ?? t("loadError")}</p>
        </div>
      </AppShell>
    );
  }

  const gazette = gazetteFormFor(form.templateId);
  const readOnly = form.approvalId !== null || form.state === "APPROVED";

  return (
    <AppShell matterId={matterId}>
      <header className="border-border bg-surface border-b px-6 py-4">
        <h1 className="font-display text-2xl font-semibold leading-tight">{tRoot(form.titleKey)}</h1>
        <div className="text-muted-ink mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span>{t("formNumber", { number: form.formNumber })}</span>
          <span aria-hidden="true">·</span>
          <span className="tabular-nums">{t("formVersion", { version: form.formVersion })}</span>
          <span aria-hidden="true">·</span>
          <span
            className={cn(
              "inline-flex min-h-6 items-center gap-1 rounded-full border px-2 text-xs font-semibold",
              formStateStyles(form.state),
            )}
          >
            {formStateIcon(form.state)}
            {tRoot(`generatedFormState.${form.state}`)}
          </span>
        </div>
      </header>

      {/* The watermark is permanent: nothing here is approved for execution. */}
      <div className="border-amber bg-amber-bg text-amber-text flex items-center gap-2 border-b px-6 py-3 font-medium">
        <TriangleAlert className="size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
        {tRoot(form.preflight.watermarkKey ?? "rta.form.watermark.draft_not_approved")}
      </div>

      {form.knownSourceDefectKeys.length > 0 && (
        <div className="border-amber bg-amber-bg text-amber-text border-b px-6 py-4">
          <div className="flex items-start gap-3">
            <Triangle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
            <div>
              <h2 className="font-semibold">{t("knownDefects")}</h2>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
                {form.knownSourceDefectKeys.map((key) => (
                  <li key={key}>{tRoot(key)}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="border-red bg-red-bg text-red mx-6 mt-6 flex gap-3 rounded border p-4 text-sm">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{error}</p>
        </div>
      )}

      {gazette ? (
        <GazetteWorkspace
          form={form}
          gazette={gazette}
          busyFieldId={processingFieldId}
          onDecision={(fieldId, decision) => void handleFieldDecision(fieldId, decision)}
        />
      ) : (
        <FieldList
          form={form}
          readOnly={readOnly}
          busyFieldId={processingFieldId}
          onDecision={(fieldId, decision) => void handleFieldDecision(fieldId, decision)}
        />
      )}

      <section className="border-border border-t px-6 py-6">
        <h2 className="mb-4 text-lg font-semibold">{t("readiness")}</h2>
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <PreflightStatus label={t("reviewReady")} ready={form.preflight.reviewReady} />
          <PreflightStatus label={t("approvalReady")} ready={form.preflight.approvalReady} />
          <PreflightStatus label={t("registrationReady")} ready={false} note={t("registrationNever")} />
        </div>

        {form.preflight.blocking.length > 0 && (
          <div className="mb-6">
            <h3 className="text-red mb-2 font-semibold">{t("blocking")}</h3>
            <ul className="space-y-2">
              {form.preflight.blocking.map((item) => (
                <PreflightItem key={`${item.code}-${item.subjectId ?? ""}`} item={item} form={form} />
              ))}
            </ul>
          </div>
        )}

        {form.preflight.warnings.length > 0 && (
          <div className="mb-6">
            <h3 className="text-amber-text mb-2 font-semibold">{t("warnings")}</h3>
            <ul className="space-y-2">
              {form.preflight.warnings.map((item) => (
                <PreflightItem key={`${item.code}-${item.subjectId ?? ""}`} item={item} form={form} />
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void handleRunPreflight()} disabled={runningPreflight}>
            {runningPreflight ? (
              <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} aria-hidden="true" />
            ) : (
              <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />
            )}
            {runningPreflight ? t("runningPreflight") : t("runPreflight")}
          </Button>
          {form.preflight.approvalReady && (
            <Link
              href={`/matters/${matterId}/drafts/${form.id}/approval`}
              className="border-forest bg-forest inline-flex min-h-10 items-center gap-2 rounded-control border px-3 py-2 font-medium text-white hover:brightness-90"
            >
              <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />
              {t("approveForm")}
            </Link>
          )}
        </div>
      </section>

      <section className="border-border border-t px-6 py-6">
        <h2 className="mb-2 text-lg font-semibold">{t("markStaleTitle")}</h2>
        <p className="text-muted-ink mb-4 text-sm">{t("markStaleBody")}</p>
        <div className="flex max-w-2xl flex-wrap gap-3">
          <label className="sr-only" htmlFor="stale-reason">
            {t("markStaleReason")}
          </label>
          <input
            id="stale-reason"
            type="text"
            placeholder={t("markStaleReason")}
            value={staleReason}
            onChange={(event) => setStaleReason(event.target.value)}
            className="border-border-control bg-surface min-w-0 flex-1 rounded-control border px-3 py-2 text-sm"
          />
          <Button onClick={() => void handleMarkStale()} disabled={markingStale}>
            {markingStale ? (
              <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} aria-hidden="true" />
            ) : (
              <AlertCircle className="size-4" strokeWidth={1.5} aria-hidden="true" />
            )}
            {t("markStale")}
          </Button>
        </div>
      </section>
    </AppShell>
  );
}

/** Field-by-field review for a template with no gazette rendering yet. */
function FieldList({
  form,
  readOnly,
  busyFieldId,
  onDecision,
}: {
  form: ApiGeneratedForm;
  readOnly: boolean;
  busyFieldId: string | null;
  onDecision: (fieldId: string, decision: FieldDecision) => void;
}) {
  const tRoot = useTranslations();
  const t = useTranslations("gazette");
  const bySection = new Map<string, ApiFormField[]>();
  for (const field of [...form.fields].sort((a, b) => a.order - b.order)) {
    bySection.set(field.sectionKey, [...(bySection.get(field.sectionKey) ?? []), field]);
  }
  return (
    <div className="divide-border max-w-4xl divide-y border-b">
      <p className="text-muted-ink px-6 pt-4 text-sm">{t("noRendering")}</p>
      {Array.from(bySection.entries()).map(([sectionKey, fields]) => (
        <section key={sectionKey} className="px-6 py-6">
          <h2 className="mb-6 text-lg font-semibold">{tRoot(sectionKey)}</h2>
          <div className="space-y-8">
            {fields.map((field) => (
              <FieldReviewCard
                key={field.id}
                field={field}
                busy={busyFieldId === field.fieldId}
                readOnly={readOnly}
                onDecision={(decision) => onDecision(field.fieldId, decision)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function PreflightStatus({ label, ready, note }: { label: string; ready: boolean; note?: string }) {
  const t = useTranslations("draft");
  return (
    <div className="border-border bg-surface rounded-card border p-4">
      <div className="flex items-center gap-2">
        {ready ? (
          <CheckCircle2 className="text-forest size-5" strokeWidth={1.5} aria-hidden="true" />
        ) : (
          <CircleDashed className="text-muted-ink size-5" strokeWidth={1.5} aria-hidden="true" />
        )}
        <span className="font-semibold">{label}</span>
      </div>
      <div className="text-muted-ink mt-1 text-sm">{ready ? t("ready") : t("notReady")}</div>
      {note && <div className="text-muted-ink mt-2 text-xs">{note}</div>}
    </div>
  );
}

function PreflightItem({ item, form }: { item: ApiPreflightItem; form: ApiGeneratedForm }) {
  const tRoot = useTranslations();
  const codeLabel = useEnumLabel("enums.preflightCode");
  const subject = item.subjectId ? form.fields.find((field) => field.fieldId === item.subjectId) : undefined;
  return (
    <li className="border-amber bg-amber-bg/50 flex gap-3 rounded border p-3 text-sm">
      <TriangleAlert className="text-amber-text mt-0.5 size-4 shrink-0" strokeWidth={1.5} aria-hidden="true" />
      <div>
        <div className="font-semibold">{subject ? tRoot(subject.labelKey) : codeLabel(item.code)}</div>
        <div className="text-muted-ink mt-1">{tRoot(item.explanationKey)}</div>
      </div>
    </li>
  );
}

function formStateStyles(state: string): string {
  switch (state) {
    case "UNRESOLVED":
    case "STALE_TEMPLATE":
    case "STALE_AFTER_APPROVAL":
      return "border-amber bg-amber-bg text-amber-text";
    case "REVIEW_READY":
    case "LAWYER_REVIEWED":
      return "border-teal bg-teal-bg text-teal";
    case "APPROVED":
      return "border-forest bg-soft-green text-forest";
    default:
      return "border-border-strong bg-surface text-ink";
  }
}

function formStateIcon(state: string) {
  switch (state) {
    case "APPROVED":
      return <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />;
    case "UNRESOLVED":
    case "STALE_TEMPLATE":
    case "STALE_AFTER_APPROVAL":
      return <AlertCircle className="size-4" strokeWidth={1.5} aria-hidden="true" />;
    default:
      return <CircleDashed className="size-4" strokeWidth={1.5} aria-hidden="true" />;
  }
}

/** Demo drafts from the older store model, which predate gazette renderings. */
function LegacyDemoDraft({ matterId, draftId }: { matterId: string; draftId: string }) {
  const t = useTranslations("draft");
  const draft = useDemoStore((state) => state.drafts.find((item) => item.id === draftId));
  return (
    <AppShell matterId={matterId}>
      {draft ? (
        <div className="border-border bg-surface m-6 max-w-4xl rounded-card border p-6">
          <h1 className="text-2xl font-semibold">{draft.title}</h1>
          <p className="text-muted-ink mt-2">{t("legacyDraftNotice")}</p>
          <Link href={`/matters/${matterId}/drafts`} className="mt-4 inline-block">
            <Button>{t("backToDrafts")}</Button>
          </Link>
        </div>
      ) : (
        <div className="border-red bg-red-bg text-red m-6 flex gap-3 rounded border p-6 text-sm">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{t("notFound")}</p>
        </div>
      )}
    </AppShell>
  );
}
