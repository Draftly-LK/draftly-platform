"use client";

import { ArrowRight, CircleAlert, CircleDashed, FileText } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { matters as demoMatters } from "@/lib/mocks";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";

const REVIEW_STATES: ReadonlySet<RtaMatterState> = new Set([
  "REVIEW_REQUIRED",
  "LEGAL_REVIEW",
  "APPROVAL_PENDING",
]);

export function RecentMatters() {
  return isApiEnabled() ? <ApiRecentMatters /> : <DemoRecentMatters />;
}

function ApiRecentMatters() {
  const result = useRecentMatters();
  return (
    <RecentMatterRows
      matters={result.matters.slice(0, 5)}
      loading={result.loading}
      failed={result.failed}
    />
  );
}

/** The offline demo's fixture matters in the API's shape. */
export function demoMatterFeed(): ApiRtaMatter[] {
  return demoMatters.map(
    (matter) =>
      ({
        id: matter.id,
        reference: matter.reference,
        clientReference: matter.parties
          .map((party) => party.nameToken)
          .join(" / "),
        state: matter.status === "in-review" ? "REVIEW_REQUIRED" : "APPROVED",
        updatedAt: matter.updatedAt,
      }) as ApiRtaMatter,
  );
}

function DemoRecentMatters() {
  return <RecentMatterRows matters={demoMatterFeed()} loading={false} failed={false} />;
}

function RecentMatterRows({
  matters,
  loading,
  failed,
}: {
  matters: ApiRtaMatter[];
  loading: boolean;
  failed: boolean;
}) {
  const t = useTranslations("home");
  const stateLabel = useTranslations("matterNav.stateLabel");
  const format = useFormatter();

  if (loading) {
    return <p className="text-muted-ink p-4 text-sm">{t("recentLoading")}</p>;
  }
  if (failed) {
    return <p className="text-red p-4 text-sm">{t("recentLoadFailed")}</p>;
  }
  if (matters.length === 0) {
    return <p className="text-muted-ink p-4 text-sm">{t("recentEmpty")}</p>;
  }

  return matters.map((matter) => {
    const needsReview = REVIEW_STATES.has(matter.state as RtaMatterState);
    const StatusIcon = needsReview ? CircleAlert : CircleDashed;
    return (
      <Link
        href={`/matters/${matter.id}`}
        key={matter.id}
        className="border-border hover:bg-hover-bg group grid min-h-[72px] grid-cols-[auto_1fr_auto] items-center gap-4 border-b px-4 last:border-b-0 md:grid-cols-[auto_1.4fr_1fr_auto]"
      >
        <span className="bg-selected-bg text-forest grid size-10 place-items-center rounded-lg">
          <FileText className="size-5" strokeWidth={1.5} aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block truncate font-semibold tabular-nums">{matter.reference}</span>
          {matter.clientReference &&
            matter.clientReference.trim().toLocaleLowerCase() !==
              matter.reference.trim().toLocaleLowerCase() && (
              <span className="text-muted-ink block truncate text-xs">{matter.clientReference}</span>
            )}
        </span>
        <span className="hidden md:block">
          <span className="sr-only">{t("status")}: </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${needsReview ? "border-amber bg-amber-bg text-amber-text" : "border-border-strong text-ink"}`}
          >
            <StatusIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
            {stateLabel(matter.state as RtaMatterState)}
          </span>
        </span>
        <span className="text-muted-ink flex items-center gap-2 text-right text-xs">
          {t("lastActivity", {
            date: format.dateTime(new Date(matter.updatedAt), {
              day: "numeric",
              month: "short",
              calendar: "gregory",
              numberingSystem: "latn",
            }),
          })}
          <ArrowRight
            className="group-hover:text-forest size-4 transition-transform group-hover:translate-x-0.5"
            strokeWidth={1.5}
            aria-hidden="true"
          />
        </span>
      </Link>
    );
  });
}
