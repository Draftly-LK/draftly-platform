import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default async function RouteSkeleton({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  const t = await getTranslations("placeholder");
  const matterId = slug[0] === "matters" && slug[1] ? slug[1] : undefined;
  const screen = slug.at(-1)?.replaceAll("-", " ") ?? t("unknown");
  return <AppShell matterId={matterId}><PageHeader title={t("title", { screen })} /><div className="p-6"><section className="rounded border border-border-strong bg-surface p-6"><p className="text-muted-ink">{t("body")}</p></section></div></AppShell>;
}
