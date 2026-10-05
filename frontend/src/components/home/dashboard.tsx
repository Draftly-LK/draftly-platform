"use client";

import { MessageSquareText } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CreateMatterLink } from "@/components/matter/create-matter-link";
import { buttonClass } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";
import { summarizeMatters } from "@/lib/home/practice-snapshot";
import { cn } from "@/lib/utils";
import type { Obligation } from "@/types/obligation";
import { CommonWorkflows } from "./common-workflows";
import { FirstRunPanel } from "./first-run-panel";
import { NavyBackdrop } from "@/components/shell/navy-backdrop";
import { Greeting } from "./greeting";
import { MatterFeed, useDashboardNow, type Feed } from "./matter-feed";
import { PracticeMetrics } from "./practice-snapshot";
import { RecentMatters } from "./recent-matters";
import { UpcomingObligations } from "./upcoming-obligations";

/** Content width: tables and grids do not stretch across a wide monitor. */
const CONTENT = "mx-auto w-full max-w-[1240px]";

export function Dashboard({ obligations }: { obligations: readonly Obligation[] }) {
  return <MatterFeed>{(feed) => <DashboardView feed={feed} obligations={obligations} />}</MatterFeed>;
}

/** Fit labels before sacrificing icons, then stack only when both labels cannot fit. */
function HeaderActions({ firstRun }: { firstRun: boolean }) {
  const t = useTranslations("home");
  const ref = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState<"icons" | "labels" | "stack">("icons");
  useEffect(() => {
    const group = ref.current;
    if (!group) return;
    const measure = () => {
      const links = [...group.querySelectorAll<HTMLAnchorElement>("a")];
      if (links.length < 2) return;
      const labelWidth = Math.max(...links.map((link) => {
        const range = document.createRange();
        range.selectNodeContents(link.querySelector("span") ?? link);
        return typeof range.getBoundingClientRect === "function" ? range.getBoundingClientRect().width : 0;
      }));
      const column = (group.clientWidth - 12) / 2;
      // 24 px horizontal padding + 2 px border; icons take another 24 px.
      setFit(column >= labelWidth + 50 ? "icons" : column >= labelWidth + 26 ? "labels" : "stack");
    };
    const observer = new ResizeObserver(measure);
    observer.observe(group);
    void document.fonts?.ready.then(measure);
    measure();
    return () => observer.disconnect();
  }, [firstRun, t]);
  return (
    <div ref={ref} className="dashboard-actions grid auto-cols-fr grid-flow-col gap-3" data-fit={fit}>
      <CreateMatterLink className="dashboard-action" />
      {!firstRun ? (
        <Link href="/assistant" className={cn(buttonClass("ghost"), "dashboard-action border-white/25 text-white hover:bg-white/10 active:bg-white/15")}>
          <MessageSquareText aria-hidden="true" className="size-4" strokeWidth={1.5} />
          <span>{t("askTitle")}</span>
        </Link>
      ) : null}
    </div>
  );
}

function DashboardView({ feed, obligations }: { feed: Feed; obligations: readonly Obligation[] }) {
  const t = useTranslations("home");
  const now = useDashboardNow();
  const ready = !feed.loading && !feed.failed;
  const firstRun = ready && feed.matters.length === 0;
  const toReview = ready ? summarizeMatters(feed.matters.map((m) => m.state)).needsReview : 0;

  const context = firstRun
    ? t("contextEmpty")
    : !ready
      ? ""
      : toReview > 0
        ? t("contextReview", { count: toReview })
        : t("contextClear");

  return (
    <>
      <section
        aria-labelledby="home-title"
        data-surface="inverse"
        // clip-path, not overflow, clips the viewport-fixed backdrop to this band.
        className="dashboard-header relative isolate bg-surface-inverse text-white [clip-path:inset(0)]"
      >
        <NavyBackdrop anchor="viewport" />
        <div className={cn(CONTENT, "dashboard-header-content relative z-10 gap-x-8 gap-y-5 px-6 py-8")}>
          <div className="dashboard-greeting min-w-0">
            <Greeting />
            <p className="dashboard-summary mt-1 min-h-6 text-base text-on-dark-muted">{context}</p>
          </div>
          {!firstRun ? <PracticeMetrics feed={feed} /> : null}
          <HeaderActions firstRun={firstRun} />
        </div>
      </section>

      <div className={cn(CONTENT, "space-y-10 px-6 py-8")}>
        {firstRun ? (
          <FirstRunPanel />
        ) : (
          <>
            <div className="grid items-start gap-8 min-[1360px]:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
              <section aria-labelledby="recent-title" className="min-w-0">
                <SectionHeader
                  id="recent-title"
                  title={t("recentTitle")}
                  action={
                    <Link href="/matters" className="font-medium text-forest hover:underline">
                      {t("viewAll")}
                    </Link>
                  }
                />
                <Card pad="none" className="overflow-hidden">
                  <RecentMatters feed={feed} now={now} />
                </Card>
              </section>
              <section aria-labelledby="obligations-title" className="min-w-0">
                <SectionHeader id="obligations-title" title={t("obligationsTitle")} />
                <UpcomingObligations obligations={obligations} feed={feed} now={now} />
              </section>
            </div>
            <CommonWorkflows />
          </>
        )}
      </div>
    </>
  );
}
