import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function NotFound() {
  const t = await getTranslations("app");
  return <main className="p-8"><h1 className="text-3xl font-semibold">{t("notFoundTitle")}</h1><p className="mt-2 text-muted-ink">{t("notFoundBody")}</p><Link className="mt-4 inline-block rounded border border-border-strong bg-surface px-4 py-2" href="/">{t("backHome")}</Link></main>;
}

