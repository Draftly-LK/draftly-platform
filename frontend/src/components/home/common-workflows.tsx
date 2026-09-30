"use client";

import { ArrowRight, CircleDashed, FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useMemo } from "react";
import { commonRtaWorkflows } from "@/lib/rta/workflow-catalogue";

/**
 * The workflows a notarial practice meets most often, on the dashboard.
 *
 * The shortlist and its order come from `COMMON_SUBTYPE_IDS` in the catalogue —
 * an editorial choice, not a measurement. Each card states whether Draftly
 * prepares that instrument in this release, so a common-but-not-yet-automated
 * workflow cannot read as available.
 */
export function CommonWorkflows() {
  const t = useTranslations("home");
  const tWorkflow = useTranslations("workflow");
  const tRoot = useTranslations();
  const workflows = useMemo(() => commonRtaWorkflows(6), []);

  if (workflows.length === 0) return null;

  return (
    <section aria-labelledby="common-workflows-title">
      <h2 id="common-workflows-title" className="text-xl font-semibold">
        {t("commonWorkflowsTitle")}
      </h2>
      <p className="text-muted-ink mt-1 max-w-3xl text-sm">{t("commonWorkflowsBody")}</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {workflows.map(({ subtype, family, available }) => {
          const TierIcon = available ? FlaskConical : CircleDashed;
          const form =
            subtype.gazetteFormNumber === null
              ? tWorkflow("noGazetteForm")
              : tWorkflow("gazetteForm", { number: subtype.gazetteFormNumber });
          const card = (
            <>
              <span className="flex items-start justify-between gap-3">
                <span className="font-heading block text-lg font-semibold">
                  {tRoot(subtype.labelKey)}
                </span>
                {available && (
                  <ArrowRight
                    className="text-muted-ink group-hover:text-forest mt-1 size-4 shrink-0"
                    strokeWidth={1.5}
                  />
                )}
              </span>
              <span className="text-muted-ink -mt-2 block text-xs">
                {tRoot(family.labelKey)} · {form}
              </span>
              <span
                className={`mt-auto inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${available ? "border-transparent bg-gold-soft text-gold-strong" : "border-border text-muted-ink"}`}
              >
                <TierIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {tWorkflow(`tier.${subtype.releaseTier}`)}
              </span>
            </>
          );
          // Only an instrument this release prepares is actionable; the rest are
          // shown for orientation and are deliberately not links.
          const cardBase = "rounded-card border-border flex min-h-32 flex-col gap-3 border p-5";
          return available ? (
            <Link
              key={subtype.id}
              href="/new"
              className={`${cardBase} bg-surface shadow-card hover:border-border-strong hover:shadow-raised group transition-shadow`}
            >
              {card}
            </Link>
          ) : (
            <div key={subtype.id} className={`${cardBase} bg-canvas`}>
              {card}
            </div>
          );
        })}
      </div>
    </section>
  );
}
