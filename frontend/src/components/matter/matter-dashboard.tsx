"use client";

import {
  ArrowRight,
  FileCheck2,
  FileText,
  ListChecks,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { listIssues } from "@/lib/api/checks";
import { type TokenProvider, apiErrorMessage } from "@/lib/api/client";
import { getDocumentInbox } from "@/lib/api/documents";
import { listForms } from "@/lib/api/drafts";
import { listMatterFacts } from "@/lib/api/facts";
import { getChecklist, getMatter } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { subtypeLabelKey } from "@/lib/rta/taxonomy";
import type { ApiChecklist, ApiDocumentInbox, ApiRtaMatter } from "@/types/rta";

/**
 * Matter dashboard, read from the live matter.
 *
 * Intake creates the matter server-side and lands here, so this is the first
 * screen a real matter shows. It answers three questions with real data: what
 * this matter is, how far the checklist has got, and what to do next.
 *
 * Every count comes from the service that owns it — the checklist owns
 * requirement state, the inbox owns files, checks own issues, drafting owns
 * forms — so nothing here infers progress an owning service has not reported.
 */
export function MatterDashboard({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  return <DashboardFlow getToken={getToken} matterId={matterId} />;
}

interface DashboardData {
  matter: ApiRtaMatter;
  /** Null until a checklist has been compiled for this matter. */
  checklist: ApiChecklist | null;
  inbox: ApiDocumentInbox | null;
  /** Null means "this section could not answer", which is not the same as 0. */
  openIssues: number | null;
  forms: number | null;
  facts: { total: number; verified: number } | null;
}

/** The next thing to do, decided from what the services actually report. */
type NextAction = "upload" | "process" | "resolve" | "draft" | "review";

function decideNextAction(data: DashboardData): NextAction {
  if ((data.inbox?.sourceFiles.length ?? 0) === 0) return "upload";
  if ((data.inbox?.unprocessedSourceFileIds.length ?? 0) > 0) return "process";
  if ((data.checklist?.blockingRequirementIds.length ?? 0) > 0) return "resolve";
  if ((data.forms ?? 0) === 0) return "draft";
  return "review";
}

function DashboardFlow({
  getToken,
  matterId,
}: {
  getToken: TokenProvider;
  matterId: string;
}) {
  const t = useTranslations("overview");
  const tNav = useTranslations("matterNav");
  const tRoot = useTranslations();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    // The matter is the only required call. The rest are per-section counts;
    // a section that cannot answer reports null rather than zero, because
    // "not known" and "none" must not render the same.
    getMatter(getToken, matterId)
      .then(async (matter) => {
        const [checklist, inbox, openIssues, forms, facts] = await Promise.all([
          getChecklist(getToken, matterId).catch(() => null),
          getDocumentInbox(getToken, matterId).catch(() => null),
          listIssues(getToken, matterId)
            .then((result) => result.items.length)
            .catch(() => null),
          listForms(getToken, matterId)
            .then((result) => result.items.length)
            .catch(() => null),
          listMatterFacts(getToken, matterId)
            .then((result) => ({
              total: result.items.filter((fact) => fact.status !== "SUPERSEDED")
                .length,
              verified: result.items.filter((fact) =>
                ["LAWYER_CONFIRMED", "LOCKED_FOR_FORM"].includes(fact.status),
              ).length,
            }))
            .catch(() => null),
        ]);
        if (!cancelled)
          setData({ matter, checklist, inbox, openIssues, forms, facts });
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(apiErrorMessage(cause, t("loadFailed")));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <p className="text-muted-ink flex items-center gap-2 p-6">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          {t("loading")}
        </p>
      </AppShell>
    );
  }

  if (error !== null || data === null) {
    return (
      <AppShell matterId={matterId}>
        <div className="mx-auto max-w-2xl p-6">
          <div className="border-red bg-red-bg text-red rounded border p-4" role="alert">
            {error ?? t("loadFailed")}
          </div>
        </div>
      </AppShell>
    );
  }

  const { matter, checklist, inbox } = data;
  // A requirement the rule pack ruled out is not work, so it is excluded from
  // the denominator rather than counted as permanently unsatisfied.
  const applicable = (checklist?.items ?? []).filter(
    (item) => item.applicability !== "NOT_APPLICABLE",
  );
  const satisfied = applicable.filter((item) => item.lifecycle === "SATISFIED").length;
  // Everything applicable that is not yet satisfied. A fresh matter has every
  // requirement at OPEN, so counting only MISSING/REQUESTED reported "nothing
  // outstanding" next to 56 blocking items.
  const outstanding = applicable.filter(
    (item) => item.lifecycle !== "SATISFIED" && item.lifecycle !== "NOT_TRIGGERED",
  ).length;
  const blocking = checklist?.blockingRequirementIds.length ?? 0;
  const percent = applicable.length === 0 ? 0 : Math.round((satisfied / applicable.length) * 100);

  const next = decideNextAction(data);
  const nextTarget: Record<NextAction, { href: string; title: string; body: string }> = {
    upload: {
      href: `/matters/${matterId}/documents`,
      title: t("nextUpload"),
      body: t("nextUploadBody"),
    },
    process: {
      href: `/matters/${matterId}/documents`,
      title: t("nextProcess"),
      body: t("nextProcessBody"),
    },
    resolve: {
      href: `/matters/${matterId}/checks`,
      title: t("nextResolve"),
      body: t("nextResolveBody"),
    },
    draft: {
      href: `/matters/${matterId}/drafts`,
      title: t("nextDraft"),
      body: t("nextDraftBody"),
    },
    review: {
      href: `/matters/${matterId}/drafts`,
      title: t("nextReview"),
      body: t("nextReviewBody"),
    },
  };
  const target = nextTarget[next];

  const subtypeKey =
    matter.subtypeId === null ? null : (subtypeLabelKey(matter.subtypeId) ?? null);
  const instrumentLabel = subtypeKey === null ? t("noSubtype") : tRoot(subtypeKey);
  const sections = [
    {
      key: "documents",
      body:
        inbox === null
          ? "—"
          : `${t("documentsCount", { count: inbox.sourceFiles.length })} · ${t("documentsPending", { count: inbox.unprocessedSourceFileIds.length })}`,
      href: `/matters/${matterId}/documents`,
      icon: FileText,
    },
    {
      key: "checks",
      body: data.openIssues === null ? "—" : t("issuesCount", { count: data.openIssues }),
      href: `/matters/${matterId}/checks`,
      icon: ListChecks,
    },
    {
      key: "facts",
      body: t("checklistSatisfied", { satisfied, total: applicable.length }),
      href: `/matters/${matterId}/facts`,
      icon: ShieldCheck,
    },
    {
      key: "drafts",
      body: data.forms === null ? "—" : t("formsCount", { count: data.forms }),
      href: `/matters/${matterId}/drafts`,
      icon: FileCheck2,
    },
  ] as const;

  return (
    <AppShell matterId={matterId}>
      <div className="p-6">
        <section className="border-border bg-surface rounded-card shadow-card overflow-hidden border">
          <div className="grid gap-6 p-6 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <div className="text-muted-ink text-xs font-semibold uppercase">
                {t("instrument")}
              </div>
              <h2 className="mt-1 text-3xl font-semibold">
                {instrumentLabel}
              </h2>
              <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
                <div>
                  <dt className="text-muted-ink text-xs">{t("matterState")}</dt>
                  <dd className="font-medium">{tNav(`stateLabel.${matter.state}`)}</dd>
                </div>
                <div>
                  <dt className="text-muted-ink text-xs">{t("scope")}</dt>
                  <dd className="font-medium">{t(`automation.${matter.automationScope}`)}</dd>
                </div>
              </dl>
              <div className="border-gold bg-canvas mt-5 rounded border-l-[3px] p-4">
                <div className="text-forest text-xs font-semibold uppercase">
                  {t("nextAction")}
                </div>
                <div className="font-heading mt-1 text-xl font-semibold">{target.title}</div>
                <p className="text-muted-ink mt-1 text-sm">{target.body}</p>
                <Link
                  href={target.href}
                  className="border-forest bg-forest mt-3 inline-flex min-h-10 items-center gap-2 rounded border px-3 py-2 font-medium text-white"
                >
                  {t("continue")}
                  <ArrowRight className="size-4" strokeWidth={1.5} />
                </Link>
              </div>
            </div>
            <div>
              <div className="text-muted-ink text-xs font-semibold uppercase">
                {t("checklistProgress")}
              </div>
              {checklist === null ? (
                <p className="text-muted-ink mt-3 text-sm">{t("noChecklist")}</p>
              ) : (
                <>
                  <div className="mt-3 flex justify-between text-sm">
                    <span>{t("checklistSatisfied", { satisfied, total: applicable.length })}</span>
                    <span className="text-muted-ink tabular-nums">{percent}%</span>
                  </div>
                  <div className="bg-disabled-bg mt-1 h-2 rounded-full">
                    <div className="bg-forest h-2 rounded-full" style={{ width: `${percent}%` }} />
                  </div>
                  <ul className="text-muted-ink mt-4 space-y-1 text-sm">
                    <li>{t("checklistBlocking", { count: blocking })}</li>
                    <li>{t("checklistMissing", { count: outstanding })}</li>
                  </ul>
                </>
              )}
            </div>
          </div>
        </section>
        <section className="border-border bg-surface rounded-card shadow-card mt-6 overflow-hidden border">
          <div className="flex items-start gap-3 border-b border-border px-5 py-4">
            <div className="bg-selected-bg text-forest grid size-9 shrink-0 place-items-center rounded">
              <Sparkles className="size-5" strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div>
              <div className="text-muted-ink text-xs font-semibold uppercase">
                {t("agentLabel")}
              </div>
              <h2 className="font-heading text-xl font-semibold">
                {t("caseSummary")}
              </h2>
              <p className="text-muted-ink mt-1 text-sm">
                {t("summaryStatus", {
                  instrument: instrumentLabel,
                  state: tNav(`stateLabel.${matter.state}`),
                })}
              </p>
            </div>
          </div>
          <dl className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-4">
            <SummaryItem
              label={t("summaryEvidence")}
              value={
                inbox === null
                  ? t("summaryUnavailable")
                  : t("summaryEvidenceValue", {
                      total: inbox.sourceFiles.length,
                      pending: inbox.unprocessedSourceFileIds.length,
                    })
              }
            />
            <SummaryItem
              label={t("summaryFacts")}
              value={
                data.facts === null
                  ? t("summaryUnavailable")
                  : t("summaryFactsValue", data.facts)
              }
            />
            <SummaryItem
              label={t("summaryRequirements")}
              value={t("summaryRequirementsValue", {
                satisfied,
                total: applicable.length,
                blocking,
                outstanding,
              })}
            />
            <SummaryItem
              label={t("summaryOutputs")}
              value={t("summaryOutputsValue", {
                issues: data.openIssues ?? 0,
                forms: data.forms ?? 0,
              })}
            />
          </dl>
          <div className="flex flex-wrap items-center gap-3 px-5 py-4">
            <p className="text-muted-ink flex-1 text-xs">{t("summaryNotice")}</p>
            <Link
              href={`/matters/${matterId}/assistant`}
              className="text-teal inline-flex min-h-10 items-center gap-2 font-medium hover:underline"
            >
              {t("openAssistant")}
              <ArrowRight className="size-4" strokeWidth={1.5} />
            </Link>
          </div>
        </section>
        <div className="divide-border border-border bg-surface mt-6 divide-y border-y">
          {sections.map(({ key, body, href, icon: Icon }) => (
            <Link
              href={href}
              key={key}
              className="hover:bg-hover-bg grid min-h-20 grid-cols-[auto_1fr_auto] items-center gap-4 px-4"
            >
              <Icon className="text-forest size-5" strokeWidth={1.5} />
              <div>
                <h2 className="font-heading text-xl font-semibold">{tNav(key)}</h2>
                <p className="text-muted-ink text-sm">{body}</p>
              </div>
              <ArrowRight className="text-muted-ink size-4" strokeWidth={1.5} />
            </Link>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface min-h-24 p-4">
      <dt className="text-muted-ink text-xs font-semibold uppercase">{label}</dt>
      <dd className="mt-2 text-sm leading-6">{value}</dd>
    </div>
  );
}
