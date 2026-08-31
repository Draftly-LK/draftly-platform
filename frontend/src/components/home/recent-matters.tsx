"use client";

import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { matters as demoMatters } from "@/lib/mocks";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";

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

function DemoRecentMatters() {
  const matters: ApiRtaMatter[] = demoMatters.map(
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
  return <RecentMatterRows matters={matters} loading={false} failed={false} />;
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

  return matters.map((matter) => (
    <Link
      href={`/matters/${matter.id}`}
      key={matter.id}
      className="border-border hover:bg-hover-bg grid min-h-16 grid-cols-[1fr_auto] items-center gap-4 border-b px-4 last:border-b-0 md:grid-cols-[1.4fr_1fr_auto]"
    >
      <span className="min-w-0">
        <span className="font-heading block truncate text-lg font-semibold">
          {matter.reference}
        </span>
        {matter.clientReference &&
          matter.clientReference.trim().toLocaleLowerCase() !==
            matter.reference.trim().toLocaleLowerCase() && (
            <span className="text-muted-ink block truncate text-xs">
              {matter.clientReference}
            </span>
          )}
      </span>
      <span className="hidden text-sm md:block">
        <span className="text-muted-ink block text-xs">{t("status")}</span>
        {stateLabel(matter.state as RtaMatterState)}
      </span>
      <span className="text-muted-ink text-right text-xs">
        {t("lastActivity", {
          date: format.dateTime(new Date(matter.updatedAt), {
            day: "numeric",
            month: "short",
          }),
        })}
      </span>
    </Link>
  ));
}
