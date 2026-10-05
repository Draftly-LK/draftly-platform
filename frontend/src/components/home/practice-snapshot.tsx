"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { Divider } from "@/components/ui/divider";
import { cn } from "@/lib/utils";
import { mattersHref, summarizeMatters, type StatusFilter } from "@/lib/home/practice-snapshot";
import type { Feed } from "./matter-feed";

/**
 * Three counts in one row, on the navy header. The number is the strongest
 * element, centred under its label; "To review" takes the amber warning colour,
 * label and number together, only while it is above zero (the label says what
 * it means, so colour is not the only signal), and zeros are muted. Gold stays reserved for the one primary
 * button. Each count opens the Matters list.
 */
export function PracticeMetrics({ feed }: { feed: Feed }) {
  const t = useTranslations("home.snapshot");
  const summary = feed.loading || feed.failed ? null : summarizeMatters(feed.matters.map((matter) => matter.state));
  const metrics = [
    { key: "open", filter: "open", value: summary?.open, flag: false },
    { key: "needsReview", filter: "review", value: summary?.needsReview, flag: (summary?.needsReview ?? 0) > 0 },
    { key: "drafting", filter: "drafting", value: summary?.drafting, flag: false },
  ] as const satisfies readonly { key: string; filter: StatusFilter; value: number | undefined; flag: boolean }[];
  return (
    <section className="dashboard-metrics" aria-label={t("title")}>
      <ul className="grid grid-cols-3 items-stretch gap-0">
        {metrics.map(({ key, filter, value, flag }, index) => (
          <li key={key} className="flex min-w-0 items-stretch">
            {index > 0 ? <Divider vertical className="bg-white/15" /> : null}
            <Link
              href={mattersHref(filter)}
              className="flex w-full min-w-0 flex-col items-center rounded px-2 py-1 text-center hover:bg-white/5"
            >
              <span className={cn("whitespace-nowrap text-xs", flag ? "text-amber-on-dark" : "text-on-dark-muted")}>{t(key)}</span>
              <span
                className={cn(
                  "block",
                  "dashboard-count mt-0.5 text-3xl font-semibold tabular-nums leading-none",
                  flag ? "text-amber-on-dark" : value ? "text-white" : "text-on-dark-muted",
                )}
              >
                {value ?? "—"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {feed.failed ? <p className="mt-2 text-xs text-red-bg">{t("failed")}</p> : null}
    </section>
  );
}
