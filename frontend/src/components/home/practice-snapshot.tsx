"use client";

import { TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Divider } from "@/components/ui/divider";
import { cn } from "@/lib/utils";
import { summarizeMatters } from "@/lib/home/practice-snapshot";
import type { Feed } from "./matter-feed";

/**
 * Three counts in one row, on the navy header. The number is the strongest
 * element; "To review" takes the amber warning colour (with an icon) only while
 * it is above zero, and zeros are muted. Gold stays reserved for the one primary
 * button. Each count opens the Matters list.
 */
// TODO: link each count to the Matters list filtered by that state once the
// list supports a filter; today all three open the unfiltered list.
export function PracticeMetrics({ feed }: { feed: Feed }) {
  const t = useTranslations("home.snapshot");
  const summary = feed.loading || feed.failed ? null : summarizeMatters(feed.matters.map((matter) => matter.state));
  const metrics = [
    { key: "open", value: summary?.open, flag: false },
    { key: "needsReview", value: summary?.needsReview, flag: (summary?.needsReview ?? 0) > 0 },
    { key: "drafting", value: summary?.drafting, flag: false },
  ] as const;
  return (
    <section aria-label={t("title")}>
      <dl className="flex items-stretch">
        {metrics.map(({ key, value, flag }, index) => (
          <div key={key} className="flex items-stretch">
            {index > 0 ? <Divider vertical className="bg-white/15" /> : null}
            <Link
              href="/matters"
              className="block rounded px-5 py-1 first:pl-0 hover:bg-white/5"
            >
              <dt className="flex items-center gap-1.5 whitespace-nowrap text-xs text-on-dark-muted">
                {flag ? <TriangleAlert aria-hidden="true" className="size-4 text-amber-on-dark" strokeWidth={1.5} /> : null}
                {t(key)}
              </dt>
              <dd
                className={cn(
                  "mt-0.5 text-3xl font-semibold tabular-nums leading-none",
                  flag ? "text-amber-on-dark" : value ? "text-white" : "text-on-dark-muted",
                )}
              >
                {value ?? "—"}
              </dd>
            </Link>
          </div>
        ))}
      </dl>
      {feed.failed ? <p className="mt-2 text-xs text-red-bg">{t("failed")}</p> : null}
    </section>
  );
}
