"use client";
import { useTranslations } from "next-intl";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { isApiEnabled } from "@/lib/api/client";
import { FactRegister } from "./fact-register";
export function FactsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("factRegister");
  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        {isApiEnabled() ? (
          <FactRegister matterId={matterId} />
        ) : (
          <p
            role="status"
            className="rounded-card border-border bg-surface border p-6 text-sm"
          >
            {t("apiUnavailable")}
          </p>
        )}
      </div>
    </AppShell>
  );
}
