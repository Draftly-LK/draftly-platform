"use client";

import { CalendarClock, CircleAlert, TriangleAlert } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { Card } from "@/components/ui/card";
import { ListRow } from "@/components/ui/list-row";
import { daysUntil, dayMonth, dueLabel, dueTone, dueWithin, sortByUrgency } from "@/lib/home/dashboard";
import type { Obligation } from "@/types/obligation";
import { cn } from "@/lib/utils";
import type { Feed } from "./matter-feed";

const TONE_TEXT = { danger: "text-red", warning: "text-amber-text", neutral: "text-muted-ink", success: "", info: "" } as const;

/**
 * What is due in the next 14 days (overdue always shows), most urgent first.
 * Overdue is danger, due within two days is warning, the rest is quiet. The
 * label is words plus an icon, never colour alone.
 */
export function UpcomingObligations({
  obligations,
  feed,
  now,
}: {
  obligations: readonly Obligation[];
  feed: Feed;
  now: Date | null;
}) {
  const t = useTranslations("home");
  const to = useTranslations("obligations");
  const format = useFormatter();
  const referenceFor = new Map(feed.matters.map((matter) => [matter.id, matter.reference]));

  if (!now) return null;
  const items = sortByUrgency(dueWithin(obligations, now));
  if (items.length === 0) return <p className="text-sm text-muted-ink">{t("obligationsEmpty")}</p>;

  return (
    <Card pad="none" className="home-timeline-surface">
      <ol className="home-timeline">
        {items.map((obligation) => {
          const days = daysUntil(obligation.dueDate, now);
          const tone = dueTone(days);
          const label = dueLabel(days);
          const Icon = tone === "danger" ? CircleAlert : tone === "warning" ? TriangleAlert : CalendarClock;
          const reference = referenceFor.get(obligation.matterId);
          return (
            <ListRow key={obligation.id} className="home-deadline-row min-h-16 items-start">
              <span aria-hidden="true" className={cn("home-timeline-node", tone === "danger" ? "bg-red-bg" : tone === "warning" ? "bg-amber-bg" : "bg-selected-bg")}><Icon aria-hidden="true" className={cn("size-4", TONE_TEXT[tone])} strokeWidth={1.5} /></span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">
                  {to(obligation.labelKey.split(".").at(-1) as "monthlyList" | "licenseRenewal" | "lawyerReview")}
                </span>
                {reference ? <span className="mt-1 block break-words font-mono text-xs text-muted-ink">{reference}</span> : null}
                <span className={cn("home-due-label mt-2 inline-flex text-xs font-semibold tabular-nums", TONE_TEXT[tone])}>
                  {label.kind === "overdue"
                    ? t("dueOverdue", { days: label.days })
                    : label.kind === "today"
                      ? t("dueToday")
                      : label.kind === "in"
                        ? t("dueIn", { days: label.days })
                        : dayMonth(format, new Date(`${obligation.dueDate}T00:00:00Z`), "UTC")}
                </span>
              </span>
            </ListRow>
          );
        })}
      </ol>
    </Card>
  );
}
