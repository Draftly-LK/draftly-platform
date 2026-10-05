"use client";

import { FileText, MessageSquareText, Play, Search, Workflow, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ActivityTimeline } from "./activity-timeline";

type Kind = "matters" | "research" | "drafts" | "workflows";
type KindFilter = "all" | Kind;

const ITEMS: readonly { kind: Kind; titleKey: "resumeMatter" | "resumeResearch" | "resumeDraft" | "resumeWorkflow"; href: string; icon: LucideIcon }[] = [
  { kind: "matters", titleKey: "resumeMatter", href: "/matters/matter-rta-001", icon: FileText },
  { kind: "research", titleKey: "resumeResearch", href: "/assistant", icon: MessageSquareText },
  { kind: "drafts", titleKey: "resumeDraft", href: "/matters/matter-rta-001/drafts/draft-form8-001", icon: Play },
  { kind: "workflows", titleKey: "resumeWorkflow", href: "/matters/matter-rta-001/workflow", icon: Workflow },
];

export function HistoryScreen() {
  const t = useTranslations("activity");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");

  const needle = query.trim().toLocaleLowerCase();
  const visible = ITEMS.filter(
    (item) => (kind === "all" || item.kind === kind) && (!needle || t(item.titleKey).toLocaleLowerCase().includes(needle)),
  );

  return (
    <AppShell>
      <PageHeader title={t("globalTitle")} description={t("globalDescription")} />
      <div className="mx-auto w-full max-w-[1240px] p-6">
        <div className="flex flex-wrap gap-3">
          <label className="sr-only" htmlFor="history-search">
            {t("search")}
          </label>
          <input
            id="history-search"
            className="border-border-control bg-surface h-10 min-w-64 flex-1 rounded-control border px-3"
            placeholder={t("search")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select
            aria-label={t("allArtifacts")}
            className="border-border-control bg-surface h-10 rounded-control border px-3"
            value={kind}
            onChange={(event) => setKind(event.target.value as KindFilter)}
          >
            <option value="all">{t("allArtifacts")}</option>
            <option value="matters">{t("matters")}</option>
            <option value="research">{t("research")}</option>
            <option value="drafts">{t("drafts")}</option>
            <option value="workflows">{t("workflows")}</option>
          </select>
        </div>
        {visible.length === 0 ? (
          <EmptyState
            icon={Search}
            title={t("noResultsTitle")}
            description={t("noResultsBody")}
            action={
              <Button
                onClick={() => {
                  setQuery("");
                  setKind("all");
                }}
              >
                {t("clearSearch")}
              </Button>
            }
          />
        ) : (
          <section className="mt-5 grid gap-3 lg:grid-cols-2">
            {visible.map(({ kind: itemKind, titleKey, href, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="border-border bg-surface hover:bg-hover-bg flex min-h-20 items-center gap-4 rounded-card border p-4"
              >
                <Icon aria-hidden="true" className="text-forest size-5" strokeWidth={1.5} />
                <span className="min-w-0 flex-1">
                  <span className="font-heading block text-lg font-semibold">{t(titleKey)}</span>
                  <span className="text-muted-ink text-xs">{t(itemKind)}</span>
                </span>
                <span className="text-forest font-medium">{t("open")}</span>
              </Link>
            ))}
          </section>
        )}
        <Card as="section" pad="lg" className="mt-6">
          <ActivityTimeline />
        </Card>
      </div>
    </AppShell>
  );
}
