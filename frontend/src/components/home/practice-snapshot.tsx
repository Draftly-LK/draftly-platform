"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { Divider } from "@/components/ui/divider";
import { cn } from "@/lib/utils";
import { countThisMonth } from "@/lib/home/insights";
import type { Feed } from "./matter-feed";
import type { ResearchOverview } from "./use-research-overview";

/**
 * Three practice totals in one row, on the navy header: every matter, every
 * research conversation, and the matters opened this month. The body's charts
 * break these down, so the header never repeats them. The number is the
 * strongest element, centred under its label, and zeros are muted. Each total
 * opens its list.
 */
export function PracticeMetrics({ feed, research, now }: { feed: Feed; research: ResearchOverview; now: Date | null }) {
  const t = useTranslations("home.snapshot");
  const ready = !feed.loading && !feed.failed;
  const metrics = [
    { key: "total", href: "/matters", value: ready ? feed.matters.length : undefined },
    { key: "research", href: "/research", value: research.conversations?.length },
    { key: "newThisMonth", href: "/matters", value: ready && now ? countThisMonth(feed.matters.map((matter) => matter.createdAt), now) : undefined },
  ] as const satisfies readonly { key: string; href: string; value: number | undefined }[];
  return (
    <section className="dashboard-metrics" aria-label={t("title")}>
      <ul className="grid grid-cols-3 items-stretch gap-0">
        {metrics.map(({ key, href, value }, index) => (
          <li key={key} className="flex min-w-0 items-stretch">
            {index > 0 ? <Divider vertical className="bg-white/15" /> : null}
            <Link
              href={href}
              className="flex w-full min-w-0 flex-col items-center rounded px-2 py-1 text-center hover:bg-white/5"
            >
              <span className="text-on-dark-muted whitespace-nowrap text-xs">{t(key)}</span>
              <span
                className={cn(
                  "block",
                  "dashboard-count mt-0.5 text-3xl font-semibold tabular-nums leading-none",
                  value ? "text-white" : "text-on-dark-muted",
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
