"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { LOCALE_COOKIE } from "@/lib/i18n/multilingual";

export function LocaleSwitch() {
  const locale = useLocale();
  const t = useTranslations("shell");
  const router = useRouter();
  const selectEnglish = () => {
    document.cookie = `${LOCALE_COOKIE}=en; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    router.refresh();
  };
  return (
    <div
      role="group"
      aria-label={t("interfaceLanguage")}
      className="border-border bg-surface rounded-control inline-flex max-w-full flex-wrap gap-0.5 border p-0.5"
    >
      <button
        type="button"
        lang="en"
        aria-label={t("englishLanguage")}
        aria-pressed={locale === "en"}
        onClick={selectEnglish}
        className="rounded-control text-muted-ink hover:bg-hover-bg aria-pressed:bg-selected-bg aria-pressed:text-forest min-h-8 px-3 py-1 text-xs font-medium transition-colors duration-150 motion-reduce:transition-none [@media(pointer:coarse)]:min-h-11"
      >
        {t("englishLanguage")}
      </button>
    </div>
  );
}
