import { FileText, MessageSquareText, Play, Workflow } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { ActivityTimeline } from "./activity-timeline";

export async function HistoryScreen() {
  const t = await getTranslations("activity");
  const items = [
    {
      title: t("resumeMatter"),
      type: t("matters"),
      href: "/matters/matter-rta-001",
      icon: FileText,
    },
    {
      title: t("resumeResearch"),
      type: t("research"),
      href: "/assistant",
      icon: MessageSquareText,
    },
    {
      title: t("resumeDraft"),
      type: t("drafts"),
      href: "/matters/matter-rta-001/drafts/draft-form8-001",
      icon: Play,
    },
    {
      title: t("resumeWorkflow"),
      type: t("workflows"),
      href: "/matters/matter-rta-001/workflow",
      icon: Workflow,
    },
  ];
  return (
    <AppShell>
      <PageHeader
        title={t("globalTitle")}
        description={t("globalDescription")}
      />
      <div className="p-6">
        <div className="flex flex-wrap gap-3">
          <label className="sr-only" htmlFor="history-search">
            {t("search")}
          </label>
          <input
            id="history-search"
            className="border-border-strong bg-surface h-10 min-w-64 flex-1 rounded-control border px-3"
            placeholder={t("search")}
          />
          <select
            aria-label={t("allArtifacts")}
            className="border-border-strong bg-surface h-10 rounded-control border px-3"
          >
            <option>{t("allArtifacts")}</option>
            <option>{t("matters")}</option>
            <option>{t("research")}</option>
            <option>{t("drafts")}</option>
            <option>{t("workflows")}</option>
          </select>
        </div>
        <section className="mt-5 grid gap-3 lg:grid-cols-2">
          {items.map(({ title, type, href, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="border-border bg-surface hover:bg-hover-bg flex min-h-20 items-center gap-4 rounded-card border p-4"
            >
              <Icon className="text-forest size-5" strokeWidth={1.5} />
              <span className="min-w-0 flex-1">
                <span className="font-heading block text-lg font-semibold">
                  {title}
                </span>
                <span className="text-muted-ink text-xs">{type}</span>
              </span>
              <span className="text-forest font-medium">{t("open")}</span>
            </Link>
          ))}
        </section>
        <section className="border-border bg-surface mt-6 rounded-card border p-6">
          <ActivityTimeline />
        </section>
      </div>
    </AppShell>
  );
}
