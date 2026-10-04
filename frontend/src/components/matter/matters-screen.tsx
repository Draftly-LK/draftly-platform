"use client";

import { FilePlus2, Plus } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { MatterFeed, type Feed } from "@/components/home/matter-feed";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button, buttonClass } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { rowLinkClass, tableRowClass } from "@/components/ui/list-row";
import { RowsSkeleton } from "@/components/ui/skeleton";
import { StatusChip } from "@/components/ui/status-chip";
import { dayMonth, stateTone } from "@/lib/home/dashboard";
import {
  matchesStatusFilter,
  mattersHref,
  parseStatusFilter,
  summarizeMatters,
  type StatusFilter,
} from "@/lib/home/practice-snapshot";
import { subtypeLabelKey } from "@/lib/rta/taxonomy";
import { cn } from "@/lib/utils";
import type { RtaMatterState } from "@/types/rta";
import { statusToneIcons } from "./status-tone-icons";

export function MattersScreen() {
  const t = useTranslations("matters");
  const tShell = useTranslations("shell");

  return (
    <AppShell>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          // The one gold button on this page.
          <Link href="/new" className={buttonClass("primary")}>
            <Plus className="size-4" strokeWidth={1.5} aria-hidden="true" />
            {tShell("create")}
          </Link>
        }
      />
      <div className="mx-auto w-full max-w-[1240px] p-6">
        {/* useSearchParams needs a Suspense boundary in a statically rendered page. */}
        <Suspense fallback={<RowsSkeleton label={t("loading")} rows={5} />}>
          <MatterFeed>{(feed) => <MatterList feed={feed} />}</MatterFeed>
        </Suspense>
      </div>
    </AppShell>
  );
}

const FILTER_LABELS = { open: "filterOpen", review: "filterReview", drafting: "filterDrafting" } as const;

function MatterList({ feed }: { feed: Feed }) {
  const t = useTranslations("matters");
  const filter = parseStatusFilter(useSearchParams().get("status"));

  if (feed.loading) return <RowsSkeleton label={t("loading")} rows={5} />;
  if (feed.failed) {
    return (
      <ErrorState
        title={t("loadFailed")}
        action={<Button onClick={() => window.location.reload()}>{t("retry")}</Button>}
      >
        {t("loadFailedHelp")}
      </ErrorState>
    );
  }
  if (feed.matters.length === 0) {
    return (
      <EmptyState
        icon={FilePlus2}
        title={t("emptyTitle")}
        description={t("emptyBody")}
        action={
          // The header already carries the page's gold button.
          <Link href="/new" className={buttonClass("secondary")}>
            {t("emptyAction")}
          </Link>
        }
      />
    );
  }

  const summary = summarizeMatters(feed.matters.map((matter) => matter.state));
  const counts: Record<StatusFilter | "all", number> = {
    all: feed.matters.length,
    open: summary.open,
    review: summary.needsReview,
    drafting: summary.drafting,
  };
  const rows = filter ? feed.matters.filter((matter) => matchesStatusFilter(matter.state, filter)) : feed.matters;

  return (
    <>
      <FilterTabs active={filter} counts={counts} />
      {rows.length === 0 ? (
        <EmptyState
          title={t("noMatchTitle")}
          description={t("noMatch")}
          action={
            <Link href={mattersHref(null)} className={buttonClass("secondary")}>
              {t("showAll")}
            </Link>
          }
        />
      ) : (
        <MatterTable rows={rows} />
      )}
    </>
  );
}

/** The filter lives in the URL (`?status=review`), so a link to a filtered list can be shared and bookmarked. */
function FilterTabs({ active, counts }: { active: StatusFilter | null; counts: Record<StatusFilter | "all", number> }) {
  const t = useTranslations("matters");
  const tabs = [
    { key: null, label: t("filterAll"), count: counts.all },
    ...(["open", "review", "drafting"] as const).map((key) => ({ key, label: t(FILTER_LABELS[key]), count: counts[key] })),
  ];
  return (
    <nav aria-label={t("filterLabel")} className="mb-4 flex flex-wrap gap-2">
      {tabs.map(({ key, label, count }) => {
        const selected = key === active;
        return (
          <Link
            key={key ?? "all"}
            href={mattersHref(key)}
            aria-current={selected ? "true" : undefined}
            className={cn(buttonClass("secondary", "sm"), selected && "border-forest bg-selected-bg font-semibold")}
          >
            {label}
            <span className="tabular-nums text-muted-ink">{count}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function MatterTable({ rows }: { rows: Feed["matters"] }) {
  const t = useTranslations("matters");
  const tRoot = useTranslations();
  const stateLabel = useTranslations("matterNav.stateLabel");
  const format = useFormatter();

  return (
    <Card pad="none" className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead className="sticky top-0 z-10 bg-canvas text-xs text-muted-ink">
          <tr className="h-10 border-b border-border">
            <th className="px-4 font-medium">{t("reference")}</th>
            <th className="px-4 font-medium">{t("clientReference")}</th>
            <th className="px-4 font-medium">{t("transaction")}</th>
            <th className="px-4 font-medium">{t("status")}</th>
            <th className="px-4 font-medium">{t("updated")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((matter) => {
            const tone = stateTone(matter.state);
            const labelKey = matter.subtypeId ? subtypeLabelKey(matter.subtypeId) : undefined;
            const updated = new Date(matter.updatedAt);
            return (
              <tr key={matter.id} className={cn(tableRowClass, "relative h-12")}>
                <td className="px-4">
                  <Link href={`/matters/${matter.id}`} className={cn(rowLinkClass, "font-semibold tabular-nums")}>
                    {matter.reference}
                    <span className="sr-only"> {t("openMatter", { reference: matter.reference })}</span>
                  </Link>
                </td>
                <td className="max-w-64 truncate px-4 text-sm">{matter.clientReference || "—"}</td>
                <td className="px-4 text-sm">{labelKey ? tRoot(labelKey) : t("notSelected")}</td>
                <td className="px-4">
                  <StatusChip tone={tone} icon={statusToneIcons[tone]} className="whitespace-nowrap">
                    {stateLabel(matter.state as RtaMatterState)}
                  </StatusChip>
                </td>
                <td className="whitespace-nowrap px-4 text-sm tabular-nums text-muted-ink">
                  {dayMonth(format, updated, "Asia/Colombo")} {format.dateTime(updated, { year: "numeric", timeZone: "Asia/Colombo", numberingSystem: "latn" })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
