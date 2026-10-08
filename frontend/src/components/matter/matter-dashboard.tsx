"use client";

import {
  ArrowRight,
  CircleCheck,
  CircleDashed,
  Compass,
  FileCheck2,
  FileText,
  ListChecks,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { buttonClass } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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
  const header = <PageHeader title={tNav("overview")} description={t("pageDescription")} />;

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
        {header}
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
        {header}
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
      href: `/matters/${matterId}/missing-documents`,
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
  const files = inbox?.sourceFiles.length ?? null;
  const pending = inbox?.unprocessedSourceFileIds.length ?? 0;
  const tiles = [
    {
      key: "documents",
      value: files,
      caption: files === null ? t("summaryUnavailable") : t("tileFiles", { count: files }),
      detail: files === null || files === 0 ? null : t("documentsPending", { count: pending }),
      href: `/matters/${matterId}/documents`,
      icon: FileText,
    },
    {
      key: "checks",
      value: data.openIssues,
      caption: data.openIssues === null ? t("summaryUnavailable") : t("tileIssues", { count: data.openIssues }),
      detail: null,
      href: `/matters/${matterId}/checks`,
      icon: ListChecks,
    },
    {
      key: "facts",
      value: data.facts?.verified ?? null,
      caption: data.facts === null ? t("summaryUnavailable") : t("tileFacts", { total: data.facts.total }),
      detail: null,
      href: `/matters/${matterId}/facts`,
      icon: ShieldCheck,
    },
    {
      key: "drafts",
      value: data.forms,
      caption: data.forms === null ? t("summaryUnavailable") : t("tileForms", { count: data.forms }),
      detail: null,
      href: `/matters/${matterId}/drafts`,
      icon: FileCheck2,
    },
  ] as const;

  return (
    <AppShell matterId={matterId}>
      {header}
      <div className="space-y-6 p-4 sm:p-6">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <section aria-labelledby="next-action-title" className="border-border bg-surface rounded-card flex flex-col border p-5 sm:p-6">
            <span className="bg-gold-soft text-gold-strong rounded-control inline-flex w-fit items-center gap-1.5 px-2.5 py-1 text-xs font-semibold">
              <Compass aria-hidden="true" className="size-3.5" strokeWidth={1.5} />
              {t("nextAction")}
            </span>
            <h2 id="next-action-title" className="font-heading mt-3 text-2xl font-semibold leading-snug">
              {target.title}
            </h2>
            <p className="text-muted-ink mt-2 max-w-prose text-sm leading-6">{target.body}</p>
            <div className="mt-5">
              <Link href={target.href} className={cn(buttonClass("primary"), "w-full sm:w-auto")}>
                {t(`action.${next}`)}
                <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
              </Link>
            </div>
            <dl className="border-border mt-6 grid grid-cols-1 gap-4 border-t pt-5 text-sm sm:grid-cols-3">
              <Detail label={t("instrument")} value={instrumentLabel} />
              <Detail label={t("matterState")} value={tNav(`stateLabel.${matter.state}`)} />
              <Detail label={t("scope")} value={t(`automation.${matter.automationScope}`)} />
            </dl>
          </section>

          <section aria-labelledby="checklist-title" className="border-border bg-surface rounded-card flex flex-col border p-5 sm:p-6">
            <h2 id="checklist-title" className="text-sm font-semibold">{t("checklistProgress")}</h2>
            {checklist === null ? (
              <p className="text-muted-ink mt-4 text-sm">{t("noChecklist")}</p>
            ) : (
              <div className="mt-4 flex flex-1 flex-wrap items-center gap-6">
                <ProgressRing percent={percent} label={t("checklistRing", { percent })} />
                <div className="min-w-0 flex-1 space-y-3 text-sm">
                  <p className="font-medium">{t("checklistSatisfied", { satisfied, total: applicable.length })}</p>
                  <p className={cn("flex items-center gap-2", blocking > 0 ? "text-amber-text" : "text-muted-ink")}>
                    {blocking > 0 ? (
                      <TriangleAlert aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
                    ) : (
                      <CircleCheck aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
                    )}
                    {t("checklistBlocking", { count: blocking })}
                  </p>
                  <p className="text-muted-ink flex items-center gap-2">
                    <CircleDashed aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
                    {t("checklistMissing", { count: outstanding })}
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>

        <ul className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          {tiles.map(({ key, value, caption, detail, href, icon: Icon }) => (
            <li key={key} className="min-w-0">
              <Link
                href={href}
                className="border-border bg-surface rounded-card hover:border-border-control group flex h-full flex-col border p-4 transition-colors duration-150 motion-reduce:transition-none sm:p-5"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2">
                    <span aria-hidden="true" className="bg-selected-bg text-forest grid size-8 shrink-0 place-items-center rounded-full">
                      <Icon className="size-4" strokeWidth={1.5} />
                    </span>
                    <span className="min-w-0 text-sm font-semibold leading-tight">{tNav(key)}</span>
                  </span>
                  <ArrowRight aria-hidden="true" className="text-muted-ink hidden size-4 shrink-0 transition-transform sm:block duration-150 group-hover:translate-x-0.5 motion-reduce:transition-none" strokeWidth={1.5} />
                </span>
                <span className="font-heading mt-4 text-3xl font-semibold tabular-nums leading-none">{value ?? "—"}</span>
                <span className="text-muted-ink mt-1.5 text-xs leading-5 sm:text-sm">{caption}</span>
                {detail ? <span className="text-muted-ink text-xs leading-5">{detail}</span> : null}
              </Link>
            </li>
          ))}
        </ul>

        <section className="border-border bg-surface rounded-card flex flex-col gap-4 border p-5 sm:flex-row sm:items-center sm:p-6">
          <span aria-hidden="true" className="bg-selected-bg text-forest grid size-10 shrink-0 place-items-center rounded-full">
            <Sparkles className="size-5" strokeWidth={1.5} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold">{t("assistantTitle")}</h2>
            <p className="text-muted-ink mt-1 text-xs leading-5">{t("summaryNotice")}</p>
          </div>
          <Link href={`/matters/${matterId}/assistant`} className={cn(buttonClass("secondary"), "w-full shrink-0 sm:w-auto")}>
            {t("openAssistant")}
            <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
          </Link>
        </section>
      </div>
    </AppShell>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-ink text-xs">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  );
}

const RING_RADIUS = 42;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

/** The checklist share as a ring; the sentence beside it carries the same numbers. */
function ProgressRing({ percent, label }: { percent: number; label: string }) {
  const length = (Math.min(100, Math.max(0, percent)) / 100) * RING_CIRCUMFERENCE;
  return (
    <div className="relative size-24 shrink-0">
      <svg viewBox="0 0 100 100" role="img" aria-label={label} className="size-full -rotate-90">
        <circle cx={50} cy={50} r={RING_RADIUS} fill="none" stroke="var(--border)" strokeWidth={10} />
        {length > 0 ? (
          <circle
            cx={50}
            cy={50}
            r={RING_RADIUS}
            fill="none"
            stroke="var(--forest)"
            strokeWidth={10}
            strokeLinecap={percent >= 100 ? "butt" : "round"}
            strokeDasharray={`${length} ${RING_CIRCUMFERENCE}`}
          />
        ) : null}
      </svg>
      <span aria-hidden="true" className="font-heading absolute inset-0 grid place-items-center text-xl font-semibold tabular-nums">
        {percent}%
      </span>
    </div>
  );
}
