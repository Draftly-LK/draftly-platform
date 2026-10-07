"use client";

import { ArrowRight } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { isApiEnabled } from "@/lib/api/client";
import { getBillingUsage } from "@/lib/api/billing";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { dayMonth, daysUntil, dueWithin } from "@/lib/home/dashboard";
import { dueByDay, pipelineSegments, researchUsage, type PipelineStage, type ResearchUsage } from "@/lib/home/insights";
import { mattersHref } from "@/lib/home/practice-snapshot";
import type { Obligation } from "@/types/obligation";
import { DayBars, DonutChart, RingChart, STAGE_COLORS } from "./charts";
import type { Feed } from "./matter-feed";

const STAGE_LABEL: Record<PipelineStage, "stageProgress" | "stageReview" | "stageDrafting"> = {
  progress: "stageProgress",
  review: "stageReview",
  drafting: "stageDrafting",
};

/** Three at-a-glance cards above the work list: pipeline, research allowance, what is due. */
export function InsightCards({ feed, obligations, now }: { feed: Feed; obligations: readonly Obligation[]; now: Date | null }) {
  const t = useTranslations("home.insights");
  return (
    <section aria-label={t("label")} className="home-insights">
      <PipelineCard feed={feed} />
      {isApiEnabled() ? <ApiResearchCard /> : <ResearchCard usage={null} state="offline" />}
      <DueCard obligations={obligations} now={now} />
    </section>
  );
}

function CardTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="text-sm font-semibold">{children}</h2>
      {action}
    </div>
  );
}

function PipelineCard({ feed }: { feed: Feed }) {
  const t = useTranslations("home.insights");
  const ready = !feed.loading && !feed.failed;
  const { open, segments } = pipelineSegments(ready ? feed.matters.map((matter) => matter.state) : []);
  const counts = Object.fromEntries(segments.map((segment) => [segment.stage, segment.count])) as Record<PipelineStage, number>;
  return (
    <Card className="home-insight-card">
      <CardTitle
        action={
          <Link href={mattersHref("open")} className="text-forest inline-flex items-center gap-1 text-xs font-medium hover:underline">
            {t("viewMatters")}
            <ArrowRight aria-hidden="true" className="size-3.5" strokeWidth={1.5} />
          </Link>
        }
      >
        {t("pipelineTitle")}
      </CardTitle>
      <div className="home-insight-body">
        <DonutChart
          label={t("pipelineChart", { open, progress: counts.progress, review: counts.review, drafting: counts.drafting })}
          segments={segments.map((segment) => ({
            key: segment.stage,
            value: segment.count,
            color: STAGE_COLORS[segment.stage],
            label: t(STAGE_LABEL[segment.stage]),
          }))}
        >
          <span className="home-insight-figure font-display font-semibold tabular-nums leading-none">{ready ? open : "–"}</span>
          <span className="text-muted-ink mt-1 text-xs">{t("open")}</span>
        </DonutChart>
        {ready && open === 0 ? (
          <p className="text-muted-ink text-sm">{t("pipelineEmpty")}</p>
        ) : (
          <ul className="w-full min-w-0 flex-1 space-y-2">
            {segments.map((segment) => (
              <li key={segment.stage} className="flex items-center gap-2 text-sm">
                <span aria-hidden="true" className="size-2.5 shrink-0 rounded-full" style={{ background: STAGE_COLORS[segment.stage] }} />
                <span className="min-w-0 flex-1 truncate">{t(STAGE_LABEL[segment.stage])}</span>
                <span className="font-semibold tabular-nums">{ready ? segment.count : "–"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function ApiResearchCard() {
  const getToken = useTokenProvider();
  const [usage, setUsage] = useState<ResearchUsage | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  useEffect(() => {
    const controller = new AbortController();
    getBillingUsage(getToken, controller.signal)
      .then((rows) => {
        setUsage(researchUsage(rows));
        setState("ready");
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("failed");
      });
    return () => controller.abort();
  }, [getToken]);
  return <ResearchCard usage={usage} state={state} />;
}

function ResearchCard({ usage, state }: { usage: ResearchUsage | null; state: "loading" | "ready" | "failed" | "offline" }) {
  const t = useTranslations("home.insights");
  const format = useFormatter();
  const used = usage?.used ?? 0;
  const limit = usage?.limit ?? null;
  const fraction = limit ? used / limit : 0;
  const ready = state === "ready" && usage !== null;
  return (
    <Card className="home-insight-card">
      <CardTitle>{t("researchTitle")}</CardTitle>
      <div className="home-insight-body">
        <RingChart
          fraction={ready ? fraction : 0}
          label={ready ? (limit ? t("researchUsed", { used, limit }) : t("researchUnlimited", { used })) : t("researchUnavailable")}
        >
          <span className="home-insight-figure font-display font-semibold tabular-nums leading-none">{ready ? used : "–"}</span>
          {ready && limit ? <span className="text-muted-ink mt-1 text-xs tabular-nums">{t("ofLimit", { limit })}</span> : null}
        </RingChart>
        <div className="w-full min-w-0 flex-1 space-y-2 text-sm">
          <p className="text-muted-ink">
            {ready
              ? limit
                ? t("researchUsed", { used, limit })
                : t("researchUnlimited", { used })
              : state === "loading"
                ? t("researchLoading")
                : t("researchUnavailable")}
          </p>
          {ready && usage.periodEnd ? (
            <p className="text-muted-ink text-xs">{t("researchResets", { date: dayMonth(format, new Date(usage.periodEnd)) })}</p>
          ) : null}
          <Link href="/research" className="text-forest inline-flex items-center gap-1 font-medium hover:underline">
            {t("openResearch")}
            <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
          </Link>
        </div>
      </div>
    </Card>
  );
}

const HORIZON_DAYS = 14;

function DueCard({ obligations, now }: { obligations: readonly Obligation[]; now: Date | null }) {
  const t = useTranslations("home.insights");
  const format = useFormatter();
  if (!now) {
    return (
      <Card className="home-insight-card">
        <CardTitle>{t("dueTitle")}</CardTitle>
      </Card>
    );
  }
  const upcoming = dueWithin(obligations, now, HORIZON_DAYS);
  const counts = dueByDay(upcoming.map((item) => item.dueDate), now, HORIZON_DAYS);
  const total = counts.reduce((sum, count) => sum + count, 0);
  const next = [...upcoming].sort((a, b) => a.dueDate.localeCompare(b.dueDate))[0];
  const titles = counts.map((count, index) => {
    const day = new Date(now.getTime() + index * 86_400_000);
    return t("dueDay", { date: dayMonth(format, day), count });
  });
  return (
    <Card className="home-insight-card">
      <CardTitle>{t("dueTitle")}</CardTitle>
      <p className="font-display text-3xl font-semibold tabular-nums leading-none">{total}</p>
      <p className="text-muted-ink mt-1 text-sm">
        {t("dueSummary", { count: total })}
        {next ? ` · ${t("dueNext", { date: dayMonth(format, new Date(`${next.dueDate}T00:00:00Z`), "UTC") })}` : ""}
      </p>
      <div className="mt-3">
        <DayBars
          counts={counts}
          titles={titles}
          label={t("dueChart", { count: total })}
          highlight={(index) => index <= 2}
        />
        <div className="text-muted-ink mt-1 flex justify-between text-[11px] tabular-nums">
          <span>{t("today")}</span>
          <span>{dayMonth(format, new Date(now.getTime() + (HORIZON_DAYS - 1) * 86_400_000))}</span>
        </div>
      </div>
      {next && daysUntil(next.dueDate, now) < 0 ? <p className="text-red mt-2 text-xs font-semibold">{t("overdueIncluded")}</p> : null}
    </Card>
  );
}
