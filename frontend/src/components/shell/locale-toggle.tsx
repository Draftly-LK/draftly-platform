"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useMultilingualEnabled } from "./multilingual-provider";

export function LocaleToggle() {
  const locale = useLocale();
  const t = useTranslations("shell");
  const multilingual = useMultilingualEnabled();
  const changeLocale = (next: "en" | "si") => {
    document.cookie = `draftly-locale=${next};path=/;max-age=31536000;samesite=lax`;
    window.location.reload();
  };
  // MULTILINGUAL_LANGUAGE_SUPPORT=false → English only, so there is nothing
  // to switch between.
  if (!multilingual) {
    return null;
  }
  return (
    <div
      aria-label={t("locale")}
      data-locale={locale}
      className="border-border-strong bg-surface inline-flex h-10 items-center rounded border p-1"
      role="group"
    >
      <Languages aria-hidden="true" className="mx-2 size-4" strokeWidth={1.5} />
      <button
        className={`h-8 min-w-10 rounded px-2 ${locale === "en" ? "bg-selected-bg text-forest font-semibold" : "text-muted-ink"}`}
        onClick={() => changeLocale("en")}
        aria-pressed={locale === "en"}
      >
        {t("english")}
      </button>
      <button
        className={`h-8 min-w-10 rounded px-2 ${locale === "si" ? "bg-selected-bg text-forest font-semibold" : "text-muted-ink"}`}
        onClick={() => changeLocale("si")}
        aria-pressed={locale === "si"}
      >
        {t("sinhala")}
      </button>
    </div>
  );
}
