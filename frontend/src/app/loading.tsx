import { getTranslations } from "next-intl/server";

export default async function Loading() {
  const t = await getTranslations("app");
  return <main aria-live="polite" className="p-8 text-muted-ink">{t("loading")}</main>;
}

