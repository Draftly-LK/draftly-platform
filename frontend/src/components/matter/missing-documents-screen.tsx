"use client";
import { FileQuestion } from "lucide-react";
import { useTranslations } from "next-intl";
import { isApiEnabled } from "@/lib/api/client";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { LiveMatterRedirect } from "./live-matter-redirect";
export function MissingDocumentsScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? <LiveMatterRedirect matterId={matterId} section="documents" /> : <OfflineMissingDocumentsScreen matterId={matterId} />;
}

function OfflineMissingDocumentsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("missingDocuments");

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border bg-surface rounded-card border p-6 text-center">
          <FileQuestion
            className="mx-auto size-12 text-muted-ink"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <h2 className="mt-4 text-lg font-semibold">{t("noChecklistEmpty")}</h2>
          <p className="text-muted-ink mt-2">{t("noChecklistEmptyBody")}</p>
        </div>
      </div>
    </AppShell>
  );
}
