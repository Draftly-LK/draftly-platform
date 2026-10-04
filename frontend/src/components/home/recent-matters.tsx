"use client";

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

const COLUMNS =
  "grid grid-cols-[minmax(0,1fr)_auto] md:grid-cols-[minmax(0,1.5fr)_minmax(0,1.1fr)_11rem_6.5rem_8rem]";

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
      <div
        aria-hidden="true"
        className={cn(COLUMNS, "hidden gap-x-4 border-b border-border bg-canvas px-4 py-2 text-xs font-medium text-muted-ink md:grid")}
      >
        <span>{t("colMatter")}</span>
        <span>{t("colInstrument")}</span>
        <span>{t("colStatus")}</span>
        <span>{t("colActivity")}</span>
        <span>{t("colNext")}</span>
      </div>
      <ul>
        {rows.map((matter) => {
          const review = needsReview(matter.state);
          const tone = stateTone(matter.state);
          const Icon = statusToneIcons[tone];
          const labelKey = matter.subtypeId ? getSubtype(matter.subtypeId)?.labelKey : undefined;
          const showReference =
            matter.clientReference && matter.clientReference.trim().toLocaleLowerCase() !== matter.reference.trim().toLocaleLowerCase();
          return (
            <ListRow key={matter.id} accent={review ? "warning" : undefined} className={cn(COLUMNS, "gap-x-4")}>
              <span className="min-w-0">
                <span className="block truncate font-medium">{showReference ? matter.clientReference : matter.reference}</span>
                {showReference ? (
                  <span className="block truncate text-xs tabular-nums text-muted-ink">{matter.reference}</span>
                ) : null}
              </span>
              <span className="hidden truncate text-sm md:block">{labelKey ? tRoot(labelKey) : "—"}</span>
              <span className="hidden md:block">
                <StatusChip tone={tone} icon={Icon} className="whitespace-nowrap">
                  {stateLabel(matter.state as RtaMatterState)}
                </StatusChip>
              </span>
              <span className="hidden text-sm tabular-nums text-muted-ink md:block">{activity(matter)}</span>
              <Link
                href={`/matters/${matter.id}`}
                className={cn(buttonClass("ghost", "sm"), rowLinkClass, "justify-self-end whitespace-nowrap")}
              >
                {review ? t("nextReview") : t("nextOpen")}
                <span className="sr-only">{matter.reference}</span>
              </Link>
            </ListRow>
          );
        })}
      </ul>
    </>
  );
}
