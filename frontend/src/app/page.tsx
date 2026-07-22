import { getTranslations } from "next-intl/server";

export default async function ScaffoldPage() {
  const t = await getTranslations("app");
  return <main className="p-8"><h1 className="text-3xl font-semibold">{t("name")}</h1></main>;
}

