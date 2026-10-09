"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { LOCALE_COOKIE } from "@/lib/i18n/multilingual";
import { Button } from "@/components/ui/button";

export function LocaleSwitch() {
  const locale = useLocale();
  const t = useTranslations("shell");
  const router = useRouter();
  const selectEnglish = () => {
    document.cookie = `${LOCALE_COOKIE}=en; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    router.refresh();
  };
  return (
    <div role="group" aria-label={t("interfaceLanguage")}>
      <Button
        variant="secondary"
        size="sm"
        lang="en"
        aria-label={t("englishLanguage")}
        aria-pressed={locale === "en"}
        onClick={selectEnglish}
      >
        {t("englishLanguage")}
      </Button>
    </div>
  );
}
