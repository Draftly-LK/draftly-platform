import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

export default async function KitchenSinkPage() {
  const t = await getTranslations("kitchen");
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="space-y-6 p-6">
        <StateSection title={t("verification")}>
          {(
            [
              "unreviewed",
              "verified",
              "corrected",
              "conflict",
              "blocked",
            ] as const
          ).map((status) => (
            <StatusBadge key={status} status={status} />
          ))}
        </StateSection>
        <StateSection title={t("processing")}>
          {(
            [
              "uploaded",
              "extracting",
              "ready-for-review",
              "failed",
              "replaced",
            ] as const
          ).map((status) => (
            <StatusBadge key={status} status={status} />
          ))}
        </StateSection>
        <StateSection title={t("checks")}>
          {(["pass", "warning", "fail", "needs-review"] as const).map(
            (status) => (
              <StatusBadge key={status} status={status} />
            ),
          )}
        </StateSection>
        <StateSection title={t("buttons")}>
          <Button variant="primary">{t("primary")}</Button>
          <Button>{t("secondary")}</Button>
          <Button disabled>{t("disabled")}</Button>
        </StateSection>
      </div>
    </AppShell>
  );
}

function StateSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-border-strong bg-surface rounded border p-5">
      <h2 className="text-2xl font-semibold">{title}</h2>
      <div className="mt-4 flex flex-wrap gap-3">{children}</div>
    </section>
  );
}
