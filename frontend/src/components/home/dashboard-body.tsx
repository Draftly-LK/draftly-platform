"use client";

import { ArrowRight, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";
import { needsReview } from "@/lib/home/dashboard";
import type { Obligation } from "@/types/obligation";
import { CommonWorkflows } from "./common-workflows";
import { FirstRunPanel } from "./first-run-panel";
import type { Feed } from "./matter-feed";
import { RecentMatters } from "./recent-matters";
import { UpcomingObligations } from "./upcoming-obligations";
import "./dashboard-body.css";

/** Body-only presentation; the header, feed and routing remain owned by Dashboard. */
export function DashboardBody({ feed, obligations, now, firstRun }: {
  feed: Feed;
  obligations: readonly Obligation[];
  now: Date | null;
  firstRun: boolean;
}) {
  const t = useTranslations("home");
  const attention = !feed.loading && !feed.failed ? feed.matters.filter((matter) => needsReview(matter.state)).length : 0;
  return (
    <div data-home-body className="mx-auto w-full max-w-[1240px] px-6 py-6">
      {firstRun ? <FirstRunPanel /> : (
        <>
          <div className="home-work-grid">
            <section aria-labelledby="recent-title" className="min-w-0">
              <SectionHeader id="recent-title" title={t("recentTitle")} description={t("body.resume")} className="home-section-heading" action={
                <Link href="/matters" className="home-view-all inline-flex min-h-10 items-center gap-1.5 font-medium text-forest hover:underline">
                  {t("viewAll")}<ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
                </Link>
              } />
              <Card pad="none" className="home-matter-surface">
                {attention > 0 ? <p className="home-attention-cue flex items-center gap-2 text-xs font-medium text-amber-text">
                  <TriangleAlert aria-hidden="true" className="size-4" strokeWidth={1.5} />
                  {t("body.needsAttention", { count: attention })}
                </p> : null}
                <RecentMatters feed={feed} now={now} />
              </Card>
            </section>
            <section aria-labelledby="obligations-title" className="home-agenda min-w-0">
              <SectionHeader id="obligations-title" title={t("obligationsTitle")} description={t("body.dueNext")} className="home-section-heading" />
              <UpcomingObligations obligations={obligations} feed={feed} now={now} />
            </section>
          </div>
          <CommonWorkflows />
        </>
      )}
    </div>
  );
}
