"use client";

import { ArrowRight, Clock3, FileText } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { ListRow, rowLinkClass } from "@/components/ui/list-row";
import { StatusChip } from "@/components/ui/status-chip";
import { buttonClass } from "@/components/ui/button";
import { statusToneIcons } from "@/components/matter/status-tone-icons";
import { activityIsRecent, dayMonth, needsReview, sortForDashboard, stateTone } from "@/lib/home/dashboard";
import { getSubtype } from "@/lib/rta/taxonomy";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";
import type { Feed } from "./matter-feed";
import { cn } from "@/lib/utils";

const ROW_LIMIT = 8;

/**
 * A list, not cards: matter, instrument, status, last activity, next action.
 * Review-required matters sort first and carry a gold-free warning accent. The
 * next action is the row's one link; its stretched hit area makes the whole row
 * clickable while keeping a single tab stop.
 */
// TODO: a per-matter next action and a property description are not in the
// matter feed yet; the action is derived from the state and the second line
// shows the reference.
export function RecentMatters({ feed, now }: { feed: Feed; now: Date | null }) {
  const t = useTranslations("home");
  const tRoot = useTranslations();
  const stateLabel = useTranslations("matterNav.stateLabel");
  const format = useFormatter();

  if (feed.loading) return <p className="p-4 text-sm text-muted-ink">{t("recentLoading")}</p>;
  if (feed.failed) return <p className="p-4 text-sm text-red">{t("recentLoadFailed")}</p>;

  const rows = sortForDashboard(feed.matters).slice(0, ROW_LIMIT);

  const activity = (matter: ApiRtaMatter) => {
    const date = new Date(matter.updatedAt);
    return now && activityIsRecent(matter.updatedAt, now)
      ? format.relativeTime(date, now)
      : dayMonth(format, date);
  };

  return (
    <>
      <ul className="home-matter-list">
        {rows.map((matter) => {
          const review = needsReview(matter.state);
          const tone = stateTone(matter.state);
          const Icon = statusToneIcons[tone];
          const labelKey = matter.subtypeId ? getSubtype(matter.subtypeId)?.labelKey : undefined;
          const showReference =
            matter.clientReference && matter.clientReference.trim().toLocaleLowerCase() !== matter.reference.trim().toLocaleLowerCase();
          return (
            <ListRow key={matter.id} accent={review ? "warning" : undefined} className="home-matter-row">
              <span aria-hidden="true" className="home-document-mark">
                <FileText className="size-5" strokeWidth={1.5} />
              </span>
              <span className="home-matter-details min-w-0">
                <span title={showReference ? matter.clientReference ?? matter.reference : matter.reference} className="home-matter-title block font-display text-lg font-semibold">{showReference ? matter.clientReference : matter.reference}</span>
                {showReference ? <span className="home-matter-reference block font-mono text-xs text-muted-ink">{matter.reference}</span> : null}
                <span className="home-matter-meta">
                  <span className="text-sm text-muted-ink">{labelKey ? tRoot(labelKey) : "?"}</span>
                  <StatusChip tone={tone} icon={Icon} className="home-state-chip">
                    {stateLabel(matter.state as RtaMatterState)}
                  </StatusChip>
                </span>
              </span>
              <span className="home-matter-next">
                <span className="home-matter-activity inline-flex items-center gap-1 text-xs tabular-nums text-muted-ink">
                  <Clock3 aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={1.5} />
                  <span>{t("body.updated")} <time dateTime={matter.updatedAt}>{activity(matter)}</time></span>
                </span>
                <Link href={`/matters/${matter.id}`} className={cn(buttonClass("ghost"), rowLinkClass, "home-row-action text-forest")}>
                  {review ? t("nextReview") : t("nextOpen")}
                  <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
                  <span className="sr-only">{matter.reference}</span>
                </Link>
              </span>
            </ListRow>
          );
        })}
      </ul>
    </>
  );
}
