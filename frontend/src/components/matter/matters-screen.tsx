"use client";

import { ArrowRight } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useDemoStore } from "@/lib/store";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { StatusBadge } from "@/components/ui/status-badge";

export function MattersScreen() {
  const t = useTranslations("matters");
  const locale = useLocale() === "si" ? "si-LK" : "en-LK";
  const matters = useDemoStore((state) => state.matters);
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border-strong bg-surface overflow-x-auto rounded border">
          <table className="w-full min-w-[980px] border-collapse whitespace-nowrap text-left">
            <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
              <tr className="border-border h-10 border-b">
                <th className="px-4 font-medium">{t("reference")}</th>
                <th className="px-4 font-medium">{t("parties")}</th>
                <th className="px-4 font-medium">{t("transaction")}</th>
                <th className="px-4 font-medium">{t("owner")}</th>
                <th className="px-4 font-medium">{t("status")}</th>
                <th className="px-4 font-medium">{t("updated")}</th>
                <th>
                  <span className="sr-only">{t("title")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {matters.map((matter) => (
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
                    {matter.parties
                      .map((party) => party.nameToken)
                      .join(" / ") || t("parties")}
                  </td>
                  <td className="px-4 text-sm">
                    {t("rta")} · {t("transfer")}
                  </td>
                  <td className="px-4 text-sm">{t("syntheticOwner")}</td>
                  <td className="px-4">
                    <StatusBadge
                      status={
                        matter.status === "in-review"
                          ? "unreviewed"
                          : "verified"
                      }
                    />
                  </td>
                  <td className="text-muted-ink px-4 text-sm tabular-nums">
                    {new Intl.DateTimeFormat(locale, {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                      timeZone: "Asia/Colombo",
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
                      <ArrowRight className="size-4" strokeWidth={1.5} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
