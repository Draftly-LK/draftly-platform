"use client";

import { useTranslations } from "next-intl";

export default function ErrorView({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useTranslations("app");
  return <main className="p-8"><h1 className="text-3xl font-semibold">{t("errorTitle")}</h1><p className="mt-2 text-muted-ink">{t("errorBody")}</p><button className="mt-4 rounded-control border border-border-strong bg-surface px-4 py-2" onClick={reset}>{t("retry")}</button></main>;
}

