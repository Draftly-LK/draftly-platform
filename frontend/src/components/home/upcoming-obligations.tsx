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
    <Card pad="none">
      <ol>
        {items.map((obligation) => {
          const days = daysUntil(obligation.dueDate, now);
          const tone = dueTone(days);
          const label = dueLabel(days);
          const Icon = tone === "danger" ? CircleAlert : tone === "warning" ? TriangleAlert : CalendarClock;
          const reference = referenceFor.get(obligation.matterId);
          return (
            <ListRow key={obligation.id} className="min-h-16 items-start">
              <Icon aria-hidden="true" className={cn("mt-0.5 size-5 shrink-0", TONE_TEXT[tone])} strokeWidth={1.5} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">
                  {to(obligation.labelKey.split(".").at(-1) as "monthlyList" | "licenseRenewal" | "lawyerReview")}
                </span>
                {reference ? <span className="block text-xs tabular-nums text-muted-ink">{reference}</span> : null}
                <span className={cn("block text-xs font-medium tabular-nums", TONE_TEXT[tone])}>
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
