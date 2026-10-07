"use client";

import { ArrowRight, BookOpenText, CalendarClock, FolderKanban, type LucideIcon } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { dayMonth, daysUntil, dueWithin } from "@/lib/home/dashboard";
import { countThisMonth, dueByDay, pipelineSegments, type PipelineStage } from "@/lib/home/insights";
import { mattersHref } from "@/lib/home/practice-snapshot";
import type { Obligation } from "@/types/obligation";
import { DayBars, DonutChart, STAGE_COLORS } from "./charts";
import type { Feed } from "./matter-feed";
import type { ResearchOverview } from "./use-research-overview";

/** Chats touched this month carry the chart navy; older ones recede to the strong border grey. */
const CHAT_COLORS = { active: STAGE_COLORS.progress, earlier: "var(--border-strong)" } as const;

const STAGE_LABEL: Record<PipelineStage, "stageProgress" | "stageReview" | "stageDrafting"> = {
  progress: "stageProgress",
  review: "stageReview",
  drafting: "stageDrafting",
};

/**
 * One card above the work list, in three panels: where the open matters are,
 * this month's research, and what is due. The header carries the totals; these
 * panels carry the detail behind them.
 */
export function PracticeInsights({ feed, obligations, now, research }: {
  feed: Feed;
  obligations: readonly Obligation[];
  now: Date | null;
  research: ResearchOverview;
}) {
  const t = useTranslations("home.insights");
  return (
    <section aria-label={t("label")} className="home-insights">
      <PipelinePanel feed={feed} />
      <ResearchPanel research={research} now={now} />
      <DuePanel obligations={obligations} now={now} />
    </section>
  );
}

function PanelTitle({ icon: Icon, children, action }: { icon: LucideIcon; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="home-insight-head">
      <span aria-hidden="true" className="home-insight-icon">
        <Icon className="size-4" strokeWidth={1.5} />
      </span>
      <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{children}</h2>
      {action}
    </div>
  );
}

function PanelLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-forest inline-flex shrink-0 items-center gap-1 text-xs font-medium hover:underline">
      {children}
      <ArrowRight aria-hidden="true" className="size-3.5" strokeWidth={1.5} />
    </Link>
  );
}

function PipelinePanel({ feed }: { feed: Feed }) {
  const t = useTranslations("home.insights");
  const ready = !feed.loading && !feed.failed;
  const { open, segments } = pipelineSegments(ready ? feed.matters.map((matter) => matter.state) : []);
  const counts = Object.fromEntries(segments.map((segment) => [segment.stage, segment.count])) as Record<PipelineStage, number>;
  return (
    <div className="home-insight-panel">
      <PanelTitle icon={FolderKanban} action={<PanelLink href={mattersHref("open")}>{t("viewMatters")}</PanelLink>}>
        {t("pipelineTitle")}
      </PanelTitle>
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
          <p className="home-insight-side text-muted-ink text-sm">{t("pipelineEmpty")}</p>
        ) : (
          <ul className="home-insight-side space-y-2.5">
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
    </div>
  );
}

function ResearchPanel({ research, now }: { research: ResearchOverview; now: Date | null }) {
  const t = useTranslations("home.insights");
  const format = useFormatter();
  const conversations = research.conversations;
  const ready = research.state === "ready" && conversations !== null && now !== null;
  const total = conversations?.length ?? 0;
  const active = ready ? countThisMonth(conversations.map((conversation) => conversation.updatedAt), now) : 0;
  const counts = { active, earlier: total - active };
  const latest = conversations?.[0] ?? null;
  const usage = research.usage;
  const questions = usage
    ? usage.limit
      ? t("researchUsed", { used: usage.used, limit: usage.limit })
      : t("researchUnlimited", { used: usage.used })
    : null;
  return (
    <div className="home-insight-panel">
      <PanelTitle icon={BookOpenText} action={<PanelLink href="/research">{t("openResearch")}</PanelLink>}>
        {t("researchTitle")}
      </PanelTitle>
      <div className="home-insight-body">
        <DonutChart
          label={ready ? t("researchChart", { total, active: counts.active, earlier: counts.earlier }) : t("researchUnavailable")}
          segments={CHAT_KEYS.map((key) => ({ key, value: counts[key], color: CHAT_COLORS[key], label: t(CHAT_LABEL[key]) }))}
        >
          <span className="home-insight-figure font-display font-semibold tabular-nums leading-none">{ready ? active : "–"}</span>
          <span className="text-muted-ink mt-1 text-xs">{t("thisMonth")}</span>
        </DonutChart>
        <div className="home-insight-side space-y-2.5 text-sm">
          {!ready ? (
            <p className="text-muted-ink">{research.state === "loading" ? t("researchLoading") : t("researchUnavailable")}</p>
          ) : total === 0 ? (
            <p className="text-muted-ink">{t("researchEmpty")}</p>
          ) : (
            <ul className="space-y-2.5">
              {CHAT_KEYS.map((key) => (
                <li key={key} className="flex items-center gap-2">
                  <span aria-hidden="true" className="size-2.5 shrink-0 rounded-full" style={{ background: CHAT_COLORS[key] }} />
                  <span className="min-w-0 flex-1 truncate">{t(CHAT_LABEL[key])}</span>
                  <span className="font-semibold tabular-nums">{counts[key]}</span>
                </li>
              ))}
            </ul>
          )}
          {ready && questions ? (
            <p className="text-muted-ink text-xs">
              {questions}
              {usage?.limit && usage.periodEnd ? ` ${t("researchResets", { date: dayMonth(format, new Date(usage.periodEnd)) })}` : ""}
            </p>
          ) : null}
          {ready && latest ? (
            <Link href="/research" className="home-insight-latest" title={latest.title}>
              <span className="text-muted-ink block text-[11px] font-medium uppercase tracking-wide">{t("latestChat")}</span>
              <span className="block truncate font-medium">{latest.title}</span>
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

const CHAT_KEYS = ["active", "earlier"] as const;
const CHAT_LABEL = { active: "chatsActive", earlier: "chatsEarlier" } as const;

const HORIZON_DAYS = 14;

function DuePanel({ obligations, now }: { obligations: readonly Obligation[]; now: Date | null }) {
  const t = useTranslations("home.insights");
  const format = useFormatter();
  if (!now) {
    return (
      <div className="home-insight-panel">
        <PanelTitle icon={CalendarClock}>{t("dueTitle")}</PanelTitle>
      </div>
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
    <div className="home-insight-panel">
      <PanelTitle icon={CalendarClock}>{t("dueTitle")}</PanelTitle>
      <div className="home-insight-due">
        <div>
          <p className="font-display text-3xl font-semibold tabular-nums leading-none">{total}</p>
          <p className="text-muted-ink mt-1 text-sm">
            {t("dueSummary", { count: total })}
            {next ? ` · ${t("dueNext", { date: dayMonth(format, new Date(`${next.dueDate}T00:00:00Z`), "UTC") })}` : ""}
          </p>
        </div>
        <div>
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
        {next && daysUntil(next.dueDate, now) < 0 ? <p className="text-red text-xs font-semibold">{t("overdueIncluded")}</p> : null}
      </div>
    </div>
  );
}
