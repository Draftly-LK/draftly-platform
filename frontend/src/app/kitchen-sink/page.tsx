import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Archive, CircleCheck, FileText, Pencil, TriangleAlert, Upload } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Select, Textarea } from "@/components/ui/field";
import { ListRow, rowLinkClass } from "@/components/ui/list-row";
import { Menu } from "@/components/ui/menu";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatusChip } from "@/components/ui/status-chip";

// Development reference only: a production build answers 404 (as dev/gazette does).
export default async function KitchenSinkPage() {
  if (process.env.NODE_ENV === "production") notFound();
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
              "UPLOAD_INITIATED",
              "QUARANTINED",
              "VALIDATED",
              "STORED",
              "PROCESSING",
              "PROCESSED",
              "PROCESSING_FAILED",
              "REJECTED",
              "SUPERSEDED",
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
          <Button variant="ghost">{t("ghost")}</Button>
          <Button variant="destructive">{t("destructive")}</Button>
          <Button size="sm">{t("small")}</Button>
          <Button variant="primary" loading>
            {t("loading")}
          </Button>
          <Button disabled>{t("disabled")}</Button>
        </StateSection>
        <StateSection title={t("fields")}>
          <div className="grid w-full max-w-3xl gap-4 md:grid-cols-2">
            <Input label={t("fieldLabel")} help={t("fieldHelp")} defaultValue="RTA-2026-ABC-0001" />
            <Input label={t("fieldLabel")} error={t("fieldError")} defaultValue="ABC" />
            <Select label={t("selectLabel")} defaultValue="transfer">
              <option value="transfer">{t("selectOption")}</option>
            </Select>
            <Input label={t("fieldLabel")} disabled defaultValue="RTA-2026-ABC-0001" />
            <Textarea label={t("textareaLabel")} wrapperClassName="md:col-span-2" />
          </div>
        </StateSection>
        <StateSection title={t("chips")}>
          <StatusChip tone="neutral" icon={FileText}>{t("toneNeutral")}</StatusChip>
          <StatusChip tone="success" icon={CircleCheck}>{t("toneSuccess")}</StatusChip>
          <StatusChip tone="warning" icon={TriangleAlert}>{t("toneWarning")}</StatusChip>
          <StatusChip tone="danger" icon={Archive}>{t("toneDanger")}</StatusChip>
          <StatusChip tone="info" icon={Pencil}>{t("toneInfo")}</StatusChip>
        </StateSection>
        <StateSection title={t("rows")}>
          <Card pad="none" className="w-full max-w-3xl">
            <ul>
              <ListRow accent="warning">
                <Link href="/matters" className={`${rowLinkClass} font-medium`}>RTA-2026-HOM-0020</Link>
                <StatusChip tone="warning" icon={TriangleAlert} className="ml-auto">{t("rowReview")}</StatusChip>
              </ListRow>
              <ListRow>
                <Link href="/matters" className={`${rowLinkClass} font-medium`}>RTA-2026-HOM-0021</Link>
                <StatusChip tone="neutral" icon={FileText} className="ml-auto">{t("toneNeutral")}</StatusChip>
              </ListRow>
            </ul>
          </Card>
        </StateSection>
        <StateSection title={t("menus")}>
          <Menu
            label={t("menuLabel")}
            trigger={t("menus")}
            triggerClassName="min-h-10 rounded-control border border-border-strong bg-surface px-4 text-sm font-medium hover:bg-hover-bg"
            items={[
              { key: "rename", label: t("menuRename"), href: "/matters" },
              { key: "archive", label: t("menuArchive"), href: "/matters" },
            ]}
          />
          <EmptyState
            icon={Upload}
            title={t("emptyTitle")}
            description={t("emptyBody")}
            action={<Button variant="primary">{t("emptyAction")}</Button>}
          />
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
