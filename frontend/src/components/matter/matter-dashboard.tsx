"use client";

import { useTranslations } from "next-intl";
import { MatterConversation } from "./matter-conversation";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { WorkChecklist } from "./work-checklist";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { isApiEnabled } from "@/lib/api/client";

/** The checklist leads the matter journey; the assistant remains one expansion away. */
export function MatterDashboard({ matterId }: { matterId: string }) {
  const t = useTranslations("overview");
  const tNav = useTranslations("matterNav");
  const tWork = useTranslations("workChecklist");
  const getToken = useTokenProvider();

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={tNav("overview")} description={t("pageDescription")} />
      <div className="space-y-4 p-4 sm:p-6">
        {isApiEnabled() && (
          <WorkChecklist
            key={matterId}
            matterId={matterId}
            getToken={getToken}
          />
        )}
        <details
          className="border-border bg-surface rounded-card overflow-hidden border"
          open={!isApiEnabled()}
        >
          <summary className="cursor-pointer p-4 font-medium">
            {tWork("assistant")}
          </summary>
          <MatterConversation key={matterId} matterId={matterId} embedded />
        </details>
      </div>
    </AppShell>
  );
}
