"use client";

import { useTranslations } from "next-intl";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { isApiEnabled } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { WorkChecklist } from "./work-checklist";

export function ChecklistScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("workChecklist");
  const tNav = useTranslations("matterNav");
  const getToken = useTokenProvider();

  return (
    <AppShell matterId={matterId}>
      <PageHeader
        title={tNav("checklist")}
        description={t("pageDescription")}
      />
      <div className="p-4 sm:p-6">
        {isApiEnabled() ? (
          <WorkChecklist
            key={matterId}
            matterId={matterId}
            getToken={getToken}
          />
        ) : (
          <p className="text-muted-ink">{t("offline")}</p>
        )}
      </div>
    </AppShell>
  );
}
