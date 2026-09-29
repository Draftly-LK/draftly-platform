import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { ActivityTimeline } from "./activity-timeline";

export async function ActivityScreen({ matterId }: { matterId: string }) {
  const t = await getTranslations("activity");
  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <section className="border-border bg-surface rounded-card border p-6 shadow-card">
          <ActivityTimeline matterId={matterId} />
        </section>
      </div>
    </AppShell>
  );
}
