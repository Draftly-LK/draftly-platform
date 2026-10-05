"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { buttonClass } from "@/components/ui/button";

export function SettingsScreen() {
  const t = useTranslations("settings");
  const [saved, setSaved] = useState(false);
  const items = ["processing", "reviews", "obligations"] as const;
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="mx-auto w-full max-w-[1240px] p-6">
        <section className="border-border border-b pb-5">
          <h2 className="text-xl font-semibold">{t("profile")}</h2>
          <p className="text-muted-ink mt-2 text-sm">{t("profileHint")}</p>
          <Link href="/profile" className={`${buttonClass("secondary")} mt-3`}>
            {t("openProfile")}
          </Link>
        </section>
        <section className="border-border border-b py-5">
          <h2 className="text-xl font-semibold">{t("notifications")}</h2>
          <div className="mt-3 space-y-2">
            {items.map((item) => (
              <label key={item} className="flex min-h-11 items-center gap-3">
                <input
                  type="checkbox"
                  defaultChecked
                  className="accent-forest size-4"
                  onChange={() => setSaved(true)}
                />
                {t(item)}
              </label>
            ))}
          </div>
          {saved && (
            <div aria-live="polite" className="text-forest mt-2 text-sm">
              {t("saved")}
            </div>
          )}
        </section>
        <section className="py-5">
          <h2 className="text-xl font-semibold">{t("language")}</h2>
          <p className="text-muted-ink mt-2">{t("reducedMotion")}</p>
        </section>
      </div>
    </AppShell>
  );
}
