"use client";

import {
  CheckCircle2,
  CircleAlert,
  CircleX,
  CreditCard,
  ReceiptText,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import {
  getBillingSubscription,
  type BillingSubscription,
} from "@/lib/api/billing";
import { isApiEnabled } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { cn } from "@/lib/utils";

type PlanKey = "solo" | "professional" | "advanced";

const PLAN_KEYS: readonly PlanKey[] = ["solo", "professional", "advanced"];

export function BillingScreen() {
  const t = useTranslations("billing");
  const format = useFormatter();
  const [subscription, setSubscription] = useState<BillingSubscription | null>(
    null,
  );

  const pilotPeriod = useMemo(() => {
    if (!subscription?.trialEndsAt) return null;
    return t("pilotPeriod", {
      start: format.dateTime(new Date(subscription.currentPeriodStart), {
        dateStyle: "medium",
      }),
      end: format.dateTime(new Date(subscription.trialEndsAt), {
        dateStyle: "medium",
      }),
    });
  }, [format, subscription, t]);

  const statusPresentation = getStatusPresentation(
    subscription?.status ?? "trialing",
    t,
  );

  return (
    <AppShell>
      {isApiEnabled() ? <SubscriptionLoader onLoad={setSubscription} /> : null}
      <PageHeader title={t("title")} description={t("description")} />
      <div className="space-y-8 p-6">
        <section className="border-border bg-surface rounded-card border p-6 shadow-card">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-muted-ink text-xs font-semibold uppercase">
                {t("currentAccess")}
              </p>
              <h2 className="mt-1 text-2xl font-semibold">{t("pilotName")}</h2>
              <p className="text-muted-ink mt-2 max-w-3xl">
                {t("pilotDescription")}
              </p>
              <p className="text-muted-ink mt-1 max-w-3xl text-sm">
                {t("pilotSupporting")}
              </p>
              {pilotPeriod ? (
                <p className="text-muted-ink mt-3 text-sm">{pilotPeriod}</p>
              ) : null}
            </div>
            <span
              className={cn(
                "inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold",
                statusPresentation.className,
              )}
            >
              <statusPresentation.Icon className="size-4" strokeWidth={1.5} />
              {statusPresentation.label}
            </span>
          </div>

          <dl className="border-border mt-6 grid gap-5 border-t pt-6 sm:grid-cols-3">
            <AccessDetail
              label={t("pilotPrice")}
              value={t("pilotPriceValue")}
            />
            <AccessDetail
              label={t("paymentMethod")}
              value={t("paymentNotRequired")}
            />
            <AccessDetail
              label={t("featureAccess")}
              value={t("fullFeatureSet")}
            />
          </dl>

          <div className="border-border bg-selected-bg mt-6 flex gap-3 rounded border p-4">
            <ShieldCheck
              className="text-forest mt-0.5 size-5 shrink-0"
              strokeWidth={1.5}
            />
            <p className="font-medium">{t("noAutomaticCharge")}</p>
          </div>
        </section>

        <section aria-labelledby="plans-after-pilot">
          <h2 id="plans-after-pilot" className="text-2xl font-semibold">
            {t("plansTitle")}
          </h2>
          <p className="text-muted-ink mt-1">{t("plansDescription")}</p>
          <div className="border-border bg-selected-bg mt-4 rounded border p-4">
            <p className="font-semibold">{t("illustrativeTitle")}</p>
            <p className="text-muted-ink mt-1 text-sm">
              {t("illustrativeBody")}
            </p>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-3">
            {PLAN_KEYS.map((plan) => (
              <PlanCard key={plan} plan={plan} />
            ))}
          </div>

          <div className="border-border bg-surface mt-5 rounded-card border p-5 shadow-card">
            <div className="flex gap-3">
              <ShieldCheck
                className="text-forest mt-0.5 size-5 shrink-0"
                strokeWidth={1.5}
              />
              <div>
                <h3 className="font-semibold">{t("qualityTitle")}</h3>
                <p className="text-muted-ink mt-1 text-sm">
                  {t("qualityBody")}
                </p>
                <p className="text-muted-ink mt-2 text-sm">
                  {t("caseLawPlanned")}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="current-billing">
          <h2 id="current-billing" className="text-2xl font-semibold">
            {t("currentBilling")}
          </h2>
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <div className="border-border bg-surface rounded-card border p-6 shadow-card">
              <CreditCard className="text-forest size-6" strokeWidth={1.5} />
              <h3 className="mt-4 text-xl font-semibold">
                {t("paymentMethod")}
              </h3>
              <p className="text-muted-ink mt-2 text-sm">{t("paymentBody")}</p>
            </div>
            <div className="border-border bg-surface rounded-card border p-6 shadow-card">
              <ReceiptText className="text-forest size-6" strokeWidth={1.5} />
              <h3 className="mt-4 text-xl font-semibold">
                {t("billingHistory")}
              </h3>
              <p className="text-muted-ink mt-2 text-sm">{t("historyBody")}</p>
            </div>
          </div>
        </section>

        <section className="border-border border-t py-5">
          <h2 className="text-lg font-semibold">{t("helpTitle")}</h2>
          <p className="text-muted-ink mt-1 text-sm">{t("helpBody")}</p>
          <Link
            href="/help"
            className="border-border-strong bg-surface hover:bg-hover-bg mt-4 inline-flex min-h-10 items-center justify-center rounded-control border px-3 py-2 font-medium"
          >
            {t("contactTeam")}
          </Link>
        </section>
      </div>
    </AppShell>
  );
}

function SubscriptionLoader({
  onLoad,
}: {
  onLoad: (subscription: BillingSubscription) => void;
}) {
  const getToken = useTokenProvider();

  useEffect(() => {
    const controller = new AbortController();
    void getBillingSubscription(getToken, controller.signal)
      .then(onLoad)
      .catch(() => {
        // Current access remains useful without the optional dates. Billing API
        // failures are deliberately quiet unless the user initiates a retry.
      });
    return () => controller.abort();
  }, [getToken, onLoad]);

  return null;
}

function AccessDetail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-ink text-xs font-semibold uppercase">
        {label}
      </dt>
      <dd className="mt-1 text-lg font-semibold">{value}</dd>
    </div>
  );
}

function PlanCard({ plan }: { plan: PlanKey }) {
  const t = useTranslations("billing");
  const recommended = plan === "professional";
  const metrics = [
    "matters",
    "documents",
    "pages",
    "storage",
    "research",
  ] as const;

  return (
    <article
      className={cn(
        "bg-surface flex h-full flex-col rounded-card border p-5 shadow-card",
        recommended ? "border-forest" : "border-border-strong",
      )}
    >
      <div className="flex min-h-7 items-start justify-between gap-3">
        <p className="text-muted-ink text-xs font-semibold uppercase">
          {t(`${plan}.eyebrow`)}
        </p>
        {recommended ? (
          <span className="border-forest bg-selected-bg text-forest inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold">
            <CheckCircle2 className="size-3.5" strokeWidth={1.5} />
            {t("recommended")}
          </span>
        ) : null}
      </div>
      <h3 className="mt-2 text-2xl font-semibold">{t(`${plan}.name`)}</h3>
      <p className="text-muted-ink mt-2 min-h-12 text-sm">
        {t(`${plan}.description`)}
      </p>
      <p className="mt-5 text-lg font-semibold">{t(`${plan}.price`)}</p>

      <dl className="border-border mt-5 divide-y border-y">
        {metrics.map((metric) => (
          <div
            key={metric}
            className="grid grid-cols-[1fr_auto] gap-3 py-3 text-sm"
          >
            <dt className="text-muted-ink">{t(`allowances.${metric}`)}</dt>
            <dd className="max-w-36 text-right font-medium">
              {t(`${plan}.${metric}`)}
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 text-sm">
        <p className="font-semibold">{t("serviceLevel")}</p>
        <p className="text-muted-ink mt-1">{t(`${plan}.service`)}</p>
        <p className="text-muted-ink mt-2">{t("draftsExportsIncluded")}</p>
      </div>

      {plan === "advanced" ? (
        <Link
          href="/help"
          className="border-border-strong bg-surface hover:bg-hover-bg mt-5 inline-flex min-h-10 items-center justify-center rounded-control border px-3 py-2 font-medium"
        >
          {t("contactUs")}
        </Link>
      ) : null}
    </article>
  );
}

function getStatusPresentation(
  status: string,
  t: ReturnType<typeof useTranslations<"billing">>,
) {
  if (["cancelled", "expired"].includes(status)) {
    return {
      Icon: CircleX,
      label: t("statusEnded"),
      className: "border-red text-red bg-surface",
    };
  }
  if (["past_due", "grace_period", "restricted"].includes(status)) {
    return {
      Icon: CircleAlert,
      label: t("statusActionNeeded"),
      className: "border-amber text-amber-text bg-amber-bg",
    };
  }
  return {
    Icon: CheckCircle2,
    label: t("statusActive"),
    className: "border-forest bg-soft-green text-forest",
  };
}
