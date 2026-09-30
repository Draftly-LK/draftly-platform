"use client";

import { ArrowRight, CircleDashed } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { subtypeLabelKey } from "@/lib/rta/taxonomy";
import { useDemoStore } from "@/lib/store";
import type { RtaMatterState } from "@/types/rta";

interface MatterRow {
  id: string;
  reference: string;
  clientReference: string | null;
  transaction: string;
  status: string;
  updatedAt: string;
}

export function MattersScreen() {
  const t = useTranslations("matters");

  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border bg-surface overflow-x-auto rounded-card border shadow-card">
          {isApiEnabled() ? <ApiMatterTable /> : <DemoMatterTable />}
        </div>
      </div>
    </AppShell>
  );
}

function ApiMatterTable() {
  const t = useTranslations("matters");
  const tRoot = useTranslations();
  const stateLabel = useTranslations("matterNav.stateLabel");
  const { matters, loading, failed } = useRecentMatters();

  const rows: MatterRow[] = matters.map((matter) => {
    const labelKey = matter.subtypeId
      ? subtypeLabelKey(matter.subtypeId)
      : undefined;
    return {
      id: matter.id,
      reference: matter.reference,
      clientReference: matter.clientReference,
      transaction: labelKey ? tRoot(labelKey) : t("notSelected"),
      status: stateLabel(matter.state as RtaMatterState),
      updatedAt: matter.updatedAt,
    };
  });

  return <MatterTable rows={rows} loading={loading} failed={failed} />;
}

function DemoMatterTable() {
  const t = useTranslations("matters");
  const matters = useDemoStore((state) => state.matters);
  const rows: MatterRow[] = matters.map((matter) => ({
    id: matter.id,
    reference: matter.reference,
    clientReference: matter.clientReference ?? null,
    transaction: t("transfer"),
    status: t("inReview"),
    updatedAt: matter.updatedAt,
  }));
  return <MatterTable rows={rows} loading={false} failed={false} />;
}

function MatterTable({
  rows,
  loading,
  failed,
}: {
  rows: MatterRow[];
  loading: boolean;
  failed: boolean;
}) {
  const t = useTranslations("matters");
  const locale = useLocale() === "si" ? "si-LK" : "en-LK";
  const message = loading
    ? t("loading")
    : failed
      ? t("loadFailed")
      : rows.length === 0
        ? t("empty")
        : null;

  return (
    <table className="w-full min-w-[760px] border-collapse whitespace-nowrap text-left">
      <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
        <tr className="border-border h-10 border-b">
          <th className="px-4 font-medium">{t("reference")}</th>
          <th className="px-4 font-medium">{t("clientReference")}</th>
          <th className="px-4 font-medium">{t("transaction")}</th>
          <th className="px-4 font-medium">{t("status")}</th>
          <th className="px-4 font-medium">{t("updated")}</th>
          <th>
            <span className="sr-only">{t("title")}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {message ? (
          <tr>
            <td
              colSpan={6}
              className="text-muted-ink h-20 px-4 text-center text-sm"
            >
              {message}
            </td>
          </tr>
        ) : (
          rows.map((matter) => (
            <tr
              key={matter.id}
              className="border-border hover:bg-hover-bg h-11 border-b last:border-b-0"
            >
              <td className="font-heading px-4 text-base font-semibold">
                <Link
                  href={`/matters/${matter.id}`}
                  className="hover:text-teal"
                >
                  {matter.reference}
                </Link>
              </td>
              <td className="max-w-64 truncate px-4 text-sm">
                {matter.clientReference || "—"}
              </td>
              <td className="px-4 text-sm">{matter.transaction}</td>
              <td className="px-4">
                <span className="border-border-strong inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold">
                  <CircleDashed
                    aria-hidden="true"
                    className="size-4"
                    strokeWidth={1.5}
                  />
                  {matter.status}
                </span>
              </td>
              <td className="text-muted-ink px-4 text-sm tabular-nums">
                {new Intl.DateTimeFormat(locale, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                  timeZone: "Asia/Colombo",
                  calendar: "gregory",
                  numberingSystem: "latn",
                }).format(new Date(matter.updatedAt))}
              </td>
              <td className="px-3">
                <Link
                  aria-label={t("openMatter", {
                    reference: matter.reference,
                  })}
                  href={`/matters/${matter.id}`}
                  className="hover:bg-active-bg grid size-9 place-items-center rounded"
                >
                  <ArrowRight
                    aria-hidden="true"
                    className="size-4"
                    strokeWidth={1.5}
                  />
                </Link>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
