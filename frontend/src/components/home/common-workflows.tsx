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
    <section aria-labelledby="common-workflows-title" className="border-border border-b py-8">
      <div className="flex items-center justify-between gap-4">
        <h2 id="common-workflows-title" className="text-2xl font-semibold">
          {t("commonWorkflowsTitle")}
        </h2>
        <Link href="/workflows" className="text-teal font-medium hover:underline">
          {t("viewAllWorkflows")}
        </Link>
      </div>
      <p className="text-muted-ink mt-1 max-w-3xl text-sm">{t("commonWorkflowsBody")}</p>
      <div className="border-border-strong bg-surface mt-3 grid overflow-hidden rounded border sm:grid-cols-2 lg:grid-cols-3">
        {workflows.map(({ subtype, family, available }, index) => {
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
              <span className="text-muted-ink mt-1 block text-xs">
                {tRoot(family.labelKey)} · {form}
              </span>
              <span className="text-muted-ink mt-3 inline-flex items-center gap-2 text-xs font-medium">
                <TierIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {tWorkflow(`tier.${subtype.releaseTier}`)}
              </span>
            </>
          );
          // Only an instrument this release prepares is actionable; the rest are
          // shown for orientation and are deliberately not links.
          const border = index > 0 ? "border-border border-t sm:border-t-0 sm:border-l" : "";
          return available ? (
            <Link
              key={subtype.id}
              href="/new"
              className={`hover:bg-hover-bg group flex min-h-28 flex-col p-5 ${border}`}
            >
              {card}
            </Link>
          ) : (
            <div key={subtype.id} className={`flex min-h-28 flex-col p-5 ${border}`}>
              {card}
            </div>
          );
        })}
      </div>
    </section>
  );
}
