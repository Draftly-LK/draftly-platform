"use client";

import { ArrowRight, FileCheck2, FileText, ListChecks, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useDemoStore } from "@/lib/store";
import { AppShell } from "@/components/shell/app-shell";

export function OverviewScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("overview");
  const matter = useDemoStore((state) => state.matters.find((item) => item.id === matterId));
  const allDocuments = useDemoStore((state) => state.documents);
  const allFacts = useDemoStore((state) => state.facts);
  const allChecks = useDemoStore((state) => state.checks);
  const allDrafts = useDemoStore((state) => state.drafts);
  const documents = allDocuments.filter((item) => item.matterId === matterId);
  const facts = allFacts.filter((item) => item.matterId === matterId);
  const checks = allChecks.filter((item) => item.matterId === matterId);
  const drafts = allDrafts.filter((item) => item.matterId === matterId);
  if (!matter) return null;
  const progress = [{ key: "examination", value: matter.progress.examination }, { key: "drafting", value: matter.progress.drafting }, { key: "execution", value: matter.progress.execution }, { key: "attestation", value: matter.progress.attestation }] as const;
  const rows = [
    { key: "documents", body: t("readyCount", { ready: documents.filter((item) => item.processingState === "ready-for-review").length, total: documents.length }), href: `/matters/${matterId}/documents`, icon: FileText },
    { key: "issues", body: t("issueCount", { count: checks.filter((check) => check.status !== "pass").length }), href: `/matters/${matterId}/checks`, icon: ListChecks },
    { key: "facts", body: t("verifiedCount", { count: facts.filter((fact) => ["verified", "corrected"].includes(fact.verificationState)).length }), href: `/matters/${matterId}/facts`, icon: ShieldCheck },
    { key: "drafts", body: t("draftCount", { count: drafts.length }), href: `/matters/${matterId}/drafts`, icon: FileCheck2 }
  ] as const;
  return <AppShell matterId={matterId}><div className="p-6"><section className="rounded border border-border-strong bg-surface"><div className="grid gap-6 p-6 lg:grid-cols-[1fr_1.2fr]"><div><div className="text-xs font-semibold uppercase text-muted-ink">{t("activeFunction")}</div><h2 className="mt-1 text-3xl font-semibold">{t("examination")}</h2><div className="mt-5 rounded border-l-2 border-forest bg-selected-bg p-4"><div className="text-xs font-semibold uppercase text-forest">{t("nextAction")}</div><div className="mt-1 font-heading text-xl font-semibold">{t("nextActionBody")}</div><Link href={`/matters/${matterId}/facts`} className="mt-3 inline-flex min-h-10 items-center gap-2 rounded border border-forest bg-forest px-3 py-2 font-medium text-white">{t("continue")}<ArrowRight className="size-4" strokeWidth={1.5} /></Link></div></div><div><div className="text-xs font-semibold uppercase text-muted-ink">{t("completion")}</div><div className="mt-3 space-y-4">{progress.map((item) => <div key={item.key}><div className="mb-1 flex justify-between text-sm"><span>{t(item.key)}</span><span className="tabular-nums text-muted-ink">{item.value}%</span></div><div className="h-2 rounded-full bg-disabled-bg"><div className="h-2 rounded-full bg-forest" style={{ width: `${item.value}%` }} /></div></div>)}</div></div></div></section><div className="mt-6 divide-y divide-border border-y border-border bg-surface">{rows.map(({ key, body, href, icon: Icon }) => <Link href={href} key={key} className="grid min-h-20 grid-cols-[auto_1fr_auto] items-center gap-4 px-4 hover:bg-hover-bg"><Icon className="size-5 text-forest" strokeWidth={1.5} /><div><h2 className="font-heading text-xl font-semibold">{t(key)}</h2><p className="text-sm text-muted-ink">{body}</p></div><span className="flex items-center gap-2 font-medium text-teal">{t("view", { section: t(key).toLowerCase() })}<ArrowRight className="size-4" strokeWidth={1.5} /></span></Link>)}<Link href={`/matters/${matterId}/activity`} className="grid min-h-20 grid-cols-[auto_1fr_auto] items-center gap-4 px-4 hover:bg-hover-bg"><ShieldCheck className="size-5 text-forest" strokeWidth={1.5} /><div><h2 className="font-heading text-xl font-semibold">{t("activity")}</h2><p className="text-sm text-muted-ink">{t("activityBody")}</p></div><ArrowRight className="size-4" /></Link></div></div></AppShell>;
}
