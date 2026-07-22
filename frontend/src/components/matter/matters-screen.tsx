"use client";

import { ArrowRight } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import Link from "next/link";
import { useDemoStore } from "@/lib/store";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { StatusBadge } from "@/components/ui/status-badge";

export function MattersScreen() {
  const t = useTranslations("matters");
  const format = useFormatter();
  const matters = useDemoStore((state) => state.matters);
  return <AppShell><PageHeader title={t("title")} description={t("description")} /><div className="p-6"><div className="overflow-x-auto rounded border border-border-strong bg-surface"><table className="w-full min-w-[760px] border-collapse text-left"><thead className="sticky top-0 z-10 bg-canvas text-xs text-muted-ink"><tr className="h-10 border-b border-border"><th className="px-4 font-medium">{t("reference")}</th><th className="px-4 font-medium">{t("parties")}</th><th className="px-4 font-medium">{t("transaction")}</th><th className="px-4 font-medium">{t("owner")}</th><th className="px-4 font-medium">{t("status")}</th><th className="px-4 font-medium">{t("updated")}</th><th><span className="sr-only">{t("title")}</span></th></tr></thead><tbody>{matters.map((matter) => <tr key={matter.id} className="h-11 border-b border-border last:border-b-0 hover:bg-hover-bg"><td className="px-4 font-heading text-base font-semibold"><Link href={`/matters/${matter.id}`} className="hover:text-teal">{matter.reference}</Link></td><td className="max-w-64 truncate px-4 text-sm">{matter.parties.map((party) => party.nameToken).join(" / ") || t("parties")}</td><td className="px-4 text-sm">{t("rta")} · {t("transfer")}</td><td className="px-4 text-sm">{t("syntheticOwner")}</td><td className="px-4"><StatusBadge status={matter.status === "in-review" ? "unreviewed" : "verified"} /></td><td className="px-4 text-sm tabular-nums text-muted-ink">{format.dateTime(new Date(matter.updatedAt), { day: "numeric", month: "short", year: "numeric" })}</td><td className="px-3"><Link aria-label={t("openMatter", { reference: matter.reference })} href={`/matters/${matter.id}`} className="grid size-9 place-items-center rounded hover:bg-active-bg"><ArrowRight className="size-4" strokeWidth={1.5} /></Link></td></tr>)}</tbody></table></div></div></AppShell>;
}

