"use client";

import { AlertCircle, ArrowRight, FilePlus2, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { generateForm, listForms } from "@/lib/api/drafts";
import { getMatter } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { DEMO_GAZETTE_FORMS } from "@/lib/gazette-forms/demo-forms";
import { useDemoStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ApiGeneratedFormSummary, ApiRtaMatter, GeneratedFormState } from "@/types/rta";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";

// Demo drafts carry the kebab-case `DraftApprovalState`; the message keys are
// camelCase, so "in-review" has to be mapped rather than used as the key.
const DEMO_STATE_KEYS = {
  working: "working",
  "in-review": "inReview",
  approved: "approved",
  exported: "exported",
} as const;

/** Map form states to icon + text badges (never color alone). */
const FORM_STATE_ICONS: Record<GeneratedFormState, typeof FilePlus2> = {
  GENERATED_DRAFT: FilePlus2,
  UNRESOLVED: AlertCircle,
  REVIEW_READY: AlertCircle,
  LAWYER_REVIEWED: AlertCircle,
  APPROVAL_PENDING: AlertCircle,
  APPROVED: AlertCircle,
  EXPORTED: AlertCircle,
  SUBMITTED: AlertCircle,
  REGISTERED: AlertCircle,
  STALE_TEMPLATE: AlertCircle,
  STALE_AFTER_APPROVAL: AlertCircle,
};

export function DraftsScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundDraftsScreen matterId={matterId} />
  ) : (
    <DemoDraftsScreen matterId={matterId} />
  );
}

function ApiBoundDraftsScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  return <DraftsScreenContent matterId={matterId} getToken={getToken} />;
}

function DemoDraftsScreen({ matterId }: { matterId: string }) {
  return <DraftsScreenContent matterId={matterId} getToken={null} />;
}

interface DraftsScreenContentProps {
  matterId: string;
  getToken: TokenProvider | null;
}

function DraftsScreenContent({ matterId, getToken }: DraftsScreenContentProps) {
  const t = useTranslations("draft");
  const tRoot = useTranslations();
  const router = useRouter();

  // State for forms and matter context
  const [forms, setForms] = useState<ApiGeneratedFormSummary[]>([]);
  const [matter, setMatter] = useState<ApiRtaMatter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  // Demo fallback
  const allDrafts = useDemoStore((state) => state.drafts);
  const isDemoMode = getToken === null;
  const demoDrafts = allDrafts.filter((draft) => draft.matterId === matterId);

  // Fetch forms and matter
  const fetchData = useCallback(async () => {
    if (isDemoMode) {
      setLoading(false);
      return;
    }
    if (getToken === null) return;

    setLoading(true);
    setError(null);
    try {
      const [formsResult, matterResult] = await Promise.all([
        listForms(getToken, matterId),
        getMatter(getToken, matterId),
      ]);
      setForms(formsResult.items);
      setMatter(matterResult);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [getToken, matterId, isDemoMode, t]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Generate a new form
  const handleGenerateForm = useCallback(async () => {
    if (isDemoMode || getToken === null) {
      // Demo mode: use the demo store
      if (!isDemoMode) return;
      // Not implemented for demo mode in this context
      return;
    }

    setGenerating(true);
    setError(null);
    try {
      const newForm = await generateForm(getToken, matterId);
      router.push(`/matters/${matterId}/drafts/${newForm.id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("generationError"));
      setGenerating(false);
    }
  }, [getToken, matterId, isDemoMode, router, t]);

  if (isDemoMode) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader
          title={t("title")}
          description={t("description")}
          action={
            demoDrafts.length === 0 && (
              <Button variant="primary" disabled>
                <FilePlus2 className="size-4" strokeWidth={1.5} />
                {t("newDraft")}
              </Button>
            )
          }
        />
        <div className="p-6">
          {demoDrafts.length === 0 ? (
            <div className="border-border-strong bg-surface rounded border p-6 text-center">
              <p className="text-muted-ink">{t("noDrafts")}</p>
            </div>
          ) : (
            <div className="border-border-strong bg-surface overflow-x-auto rounded border">
              <table className="w-full min-w-[900px] border-collapse whitespace-nowrap text-left">
                <thead className="bg-canvas text-muted-ink text-xs">
                  <tr className="border-border h-10 border-b">
                    <th className="px-4">{t("draftTitle")}</th>
                    <th className="px-4">{t("template")}</th>
                    <th className="px-4">{t("version")}</th>
                    <th className="px-4">{t("state")}</th>
                    <th className="px-4">{t("actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {demoDrafts.map((draft) => (
                    <tr
                      key={draft.id}
                      className="border-border h-11 border-b last:border-b-0"
                    >
                      <td className="font-heading px-4 text-lg font-semibold">
                        {draft.title}
                      </td>
                      <td className="px-4">{t("form8Name")}</td>
                      <td className="px-4 tabular-nums">
                        v{draft.versions.length} ·{" "}
                        {
                          draft.versions.find(
                            (version) => version.id === draft.activeVersionId,
                          )?.hash
                        }
                      </td>
                      <td className="px-4">
                        <span className="border-border-strong inline-flex rounded-full border px-2 py-1 text-xs font-semibold">
                          {t(DEMO_STATE_KEYS[draft.approvalState])}
                        </span>
                      </td>
                      <td className="px-4">
                        <Link
                          className="border-border-strong hover:bg-hover-bg inline-flex min-h-8 items-center gap-2 rounded border px-3"
                          href={`/matters/${matterId}/drafts/${draft.id}`}
                        >
                          {t("open")}
                          <ArrowRight className="size-4" strokeWidth={1.5} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <DemoGazetteForms matterId={matterId} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell matterId={matterId}>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          <Button variant="primary" disabled={loading || generating} onClick={() => void handleGenerateForm()}>
            {generating ? (
              <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
            ) : (
              <FilePlus2 className="size-4" strokeWidth={1.5} />
            )}
            {t("newDraft")}
          </Button>
        }
      />

      {error && (
        <div className="mx-6 mt-6 flex gap-3 rounded border border-red bg-red-bg p-4 text-sm text-red">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{error}</p>
        </div>
      )}

      <div className="p-6">
        {loading ? (
          <div className="flex items-center gap-2 text-muted-ink">
            <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
            {t("loading")}
          </div>
        ) : forms.length === 0 ? (
          <div className="border-border-strong bg-surface rounded border p-6 text-center">
            <p className="text-muted-ink">{t("noDrafts")}</p>
          </div>
        ) : (
          <div className="border-border-strong bg-surface overflow-x-auto rounded border">
            <table className="w-full min-w-[900px] border-collapse whitespace-nowrap text-left">
              <thead className="bg-canvas text-muted-ink text-xs">
                <tr className="border-border h-10 border-b">
                  <th className="px-4">{t("template")}</th>
                  <th className="px-4">{t("version")}</th>
                  <th className="px-4">{t("state")}</th>
                  <th className="px-4">{t("updated")}</th>
                  <th className="px-4">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {forms.map((form) => {
                  const StateIcon = FORM_STATE_ICONS[form.state];
                  const formattedDate = new Date(form.createdAt).toLocaleDateString();
                  return (
                    <tr
                      key={form.id}
                      className="border-border h-11 border-b last:border-b-0"
                    >
                      <td className="px-4">{tRoot(matter?.subtypeId ? `rta.subtype.${matter.subtypeId}` : "label.form")}</td>
                      <td className="px-4 tabular-nums">v{form.formVersion}</td>
                      <td className="px-4">
                        <span className={cn(
                          "inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold",
                          getFormStateStyles(form.state)
                        )}>
                          <StateIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
                          {tRoot(`generatedFormState.${form.state}`)}
                        </span>
                      </td>
                      <td className="px-4 text-sm">{formattedDate}</td>
                      <td className="px-4">
                        <Link
                          className="border-border-strong hover:bg-hover-bg inline-flex min-h-8 items-center gap-2 rounded border px-3"
                          href={`/matters/${matterId}/drafts/${form.id}`}
                        >
                          {t("open")}
                          <ArrowRight className="size-4" strokeWidth={1.5} />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function getFormStateStyles(state: GeneratedFormState): string {
  switch (state) {
    case "GENERATED_DRAFT":
      return "border-border-strong bg-surface text-ink";
    case "UNRESOLVED":
      return "border-amber bg-amber-bg text-amber-text";
    case "REVIEW_READY":
      return "border-teal bg-teal-bg text-teal";
    case "APPROVED":
      return "border-forest bg-soft-green text-forest";
    case "EXPORTED":
    case "REGISTERED":
      return "border-forest bg-soft-green text-forest";
    case "STALE_TEMPLATE":
    case "STALE_AFTER_APPROVAL":
      return "border-amber bg-amber-bg text-amber-text";
    default:
      return "border-border-strong bg-surface text-ink";
  }
}

/** The synthetic gazette forms, so the offline demo can open both drafting modes. */
function DemoGazetteForms({ matterId }: { matterId: string }) {
  const t = useTranslations("draft");
  const tRoot = useTranslations();
  const forms = DEMO_GAZETTE_FORMS.filter((form) => form.matterId === matterId);
  if (forms.length === 0) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-lg font-semibold">{t("gazetteForms")}</h2>
      <ul className="border-border-strong bg-surface divide-border divide-y rounded border">
        {forms.map((form) => (
          <li key={form.id} className="flex min-h-11 flex-wrap items-center gap-3 px-4 py-2">
            <span className="font-medium">{tRoot(form.titleKey)}</span>
            <span className="text-muted-ink text-sm">{t("formNumber", { number: form.formNumber })}</span>
            <Link
              className="border-border-strong hover:bg-hover-bg ml-auto inline-flex min-h-8 items-center gap-2 rounded border px-3"
              href={`/matters/${matterId}/drafts/${form.id}`}
            >
              {t("open")}
              <ArrowRight className="size-4" strokeWidth={1.5} aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
