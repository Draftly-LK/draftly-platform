"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { LOCALE_COOKIE, type UiLocale } from "@/lib/i18n/multilingual";

export function LocaleSwitch() {
  const locale = useLocale();
  const t = useTranslations("shell");
  const router = useRouter();
  const select = (next: UiLocale) => {
    document.cookie = `${LOCALE_COOKIE}=${next}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    router.refresh();
  };
  return (
    <div
      role="group"
      aria-label={t("interfaceLanguage")}
      className="rail:justify-center mb-2 flex flex-wrap gap-1"
    >
      {(["en", "si"] as const).map((value) => (
        <button
          key={value}
          type="button"
          lang={value}
          aria-label={
            value === "en" ? t("englishLanguage") : t("sinhalaLanguage")
          }
          aria-pressed={locale === value}
          onClick={() => select(value)}
          className="rounded-control text-on-dark px-2 py-2 text-xs hover:bg-white/10 aria-pressed:bg-white/10"
        >
          <span className="rail:hidden">
            {value === "en" ? t("englishLanguage") : t("sinhalaLanguage")}
          </span>
          <span aria-hidden="true" className="rail:inline hidden">
            {value === "en" ? t("englishShort") : t("sinhalaShort")}
          </span>
        </button>
      ))}
    </div>
  );
}
