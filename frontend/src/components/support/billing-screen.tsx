"use client";

import { CheckCircle2, CreditCard, ReceiptText } from "lucide-react";
import { useTranslations } from "next-intl";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export function BillingScreen() {
  const t = useTranslations("billing");
  const features = ["matters", "documents", "workflows"] as const;

  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="mx-auto max-w-4xl space-y-6 p-6">
        <section className="border-border bg-surface rounded-card border p-6 shadow-card">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-muted-ink text-xs font-semibold uppercase">
                {t("currentPlan")}
              </p>
              <h2 className="mt-1 text-2xl font-semibold">{t("planName")}</h2>
              <p className="text-muted-ink mt-2 max-w-2xl">
                {t("planDescription")}
              </p>
            </div>
            <span className="border-forest bg-soft-green text-forest inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold">
              <CheckCircle2 className="size-4" strokeWidth={1.5} />
              {t("active")}
            </span>
          </div>
          <div className="border-border mt-6 grid gap-6 border-t pt-6 md:grid-cols-2">
            <div>
              <p className="text-2xl font-semibold">{t("price")}</p>
              <p className="text-muted-ink mt-1 text-sm">{t("priceDetail")}</p>
            </div>
            <div>
              <h3 className="font-semibold">{t("features")}</h3>
              <ul className="mt-2 space-y-2 text-sm">
                {features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <CheckCircle2
                      className="text-forest size-4 shrink-0"
                      strokeWidth={1.5}
                    />
                    {t(feature)}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          <section className="border-border bg-surface rounded-card border p-6 shadow-card">
            <CreditCard className="text-forest size-6" strokeWidth={1.5} />
            <h2 className="mt-4 text-xl font-semibold">{t("paymentMethod")}</h2>
            <p className="text-muted-ink mt-2 text-sm">{t("paymentEmpty")}</p>
          </section>
          <section className="border-border bg-surface rounded-card border p-6 shadow-card">
            <ReceiptText className="text-forest size-6" strokeWidth={1.5} />
            <h2 className="mt-4 text-xl font-semibold">{t("billingHistory")}</h2>
            <p className="text-muted-ink mt-2 text-sm">{t("historyEmpty")}</p>
          </section>
        </div>

        <section className="border-border border-t py-5">
          <h2 className="text-lg font-semibold">{t("contact")}</h2>
          <p className="text-muted-ink mt-1 text-sm">{t("contactBody")}</p>
        </section>
      </div>
    </AppShell>
  );
}
