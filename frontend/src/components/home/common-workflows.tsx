"use client";

import { ArrowRight, ArrowLeftRight, FileCheck2, FileText, Gift, Handshake, KeyRound, Landmark, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useMemo } from "react";
import { SectionHeader } from "@/components/ui/section-header";
import { commonRtaWorkflows, type RtaWorkflow } from "@/lib/rta/workflow-catalogue";

const ICONS: Record<string, LucideIcon> = {
  transfer_sale: ArrowLeftRight,
  mortgage: Landmark,
  mortgage_cancel: FileCheck2,
  lease: KeyRound,
  gift: Gift,
  sale_agreement: Handshake,
};

const DESCRIPTION_KEYS = ["transfer_sale", "mortgage", "mortgage_cancel", "lease", "gift", "sale_agreement"] as const;
type DescriptionKey = (typeof DESCRIPTION_KEYS)[number];

function slug(workflow: RtaWorkflow): string {
  return workflow.subtype.id.split(".").at(-1) ?? "";
}

/** The shortlist and its order come from `COMMON_SUBTYPE_IDS`: an editorial choice, not a measurement. */
export function useCommonWorkflows() {
  return useMemo(() => {
    const all = commonRtaWorkflows(6);
    return { available: all.filter((w) => w.available), planned: all.filter((w) => !w.available) };
  }, []);
}

/** One available workflow as a whole-card link. Shared with the first-run panel. */
export function WorkflowCard({ workflow }: { workflow: RtaWorkflow }) {
  const t = useTranslations("home");
  const tWorkflow = useTranslations("workflow");
  const tRoot = useTranslations();
  const key = slug(workflow);
  const Icon = ICONS[key] ?? FileText;
  const form = workflow.subtype.gazetteFormNumber;
  return (
    <Link
      href="/new"
      className="home-workflow-tile rounded-card border border-border bg-surface"
    >
      <span className="home-workflow-top">
        <span aria-hidden="true" className="home-workflow-document"><Icon className="size-5" strokeWidth={1.5} /></span>
        <span className="home-form-reference text-xs text-muted-ink">
          {form === null ? tWorkflow("noGazetteForm") : tWorkflow("gazetteForm", { number: form })}
        </span>
      </span>
      <span className="home-workflow-title font-display text-lg font-semibold">{tRoot(workflow.subtype.labelKey)}</span>
      {(DESCRIPTION_KEYS as readonly string[]).includes(key) ? (
        <span className="home-workflow-description text-sm text-muted-ink">{t(`workflowDescription.${key as DescriptionKey}`)}</span>
      ) : null}
      <span className="home-workflow-start inline-flex items-center gap-2 text-sm font-semibold text-forest">
        {t("body.start")} <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
      </span>
    </Link>
  );
}

/**
 * What can be started now, as cards; what is planned, as a quiet "Coming soon"
 * line that is neither a link nor focusable.
 */
export function CommonWorkflows() {
  const t = useTranslations("home");
  const tWorkflow = useTranslations("workflow");
  const tRoot = useTranslations();
  const { available, planned } = useCommonWorkflows();

  if (available.length === 0 && planned.length === 0) return null;

  return (
    <section aria-labelledby="common-workflows-title" className="home-workflows">
      <SectionHeader id="common-workflows-title" title={t("commonWorkflowsTitle")} className="home-section-heading" />
      <div className="home-live-workflows grid gap-4 sm:grid-cols-2">
        {available.map((workflow) => (
          <WorkflowCard key={workflow.subtype.id} workflow={workflow} />
        ))}
      </div>
      {planned.length > 0 ? (
        <section aria-labelledby="coming-soon-title" className="home-planned-workflows">
          <h3 id="coming-soon-title" className="mb-3 text-sm font-semibold text-muted-ink">{t("comingSoon")}</h3>
          <ul className="home-planned-grid" aria-label={t("body.planned")}>
            {planned.map((workflow) => {
              const Icon = ICONS[slug(workflow)] ?? FileText;
              return <li key={workflow.subtype.id} className="home-planned-item cursor-default">
                <span role="link" aria-disabled="true" className="flex items-center gap-3">
                  <Icon aria-hidden="true" className="size-4 shrink-0 text-muted-ink" strokeWidth={1.5} />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-muted-ink">{tRoot(workflow.subtype.labelKey)}</span>
                    {workflow.subtype.gazetteFormNumber !== null ? (
                      <span className="mt-1 block text-xs text-muted-ink">{tWorkflow("gazetteForm", { number: workflow.subtype.gazetteFormNumber })}</span>
                    ) : null}
                  </span>
                </span>
              </li>;
            })}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
