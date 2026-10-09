"use client";

import { useTranslations } from "next-intl";
import { MatterConversation } from "./matter-conversation";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

/** The live matter overview keeps the matter assistant as its only content. */
export function MatterDashboard({ matterId }: { matterId: string }) {
  const t = useTranslations("overview");
  const tNav = useTranslations("matterNav");

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={tNav("overview")} description={t("pageDescription")} />
      <div className="p-4 sm:p-6">
        <section className="border-border bg-surface rounded-card overflow-hidden border">
          <MatterConversation key={matterId} matterId={matterId} embedded />
        </section>
      </div>
    </AppShell>
  );
}
