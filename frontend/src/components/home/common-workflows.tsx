"use client";

import { ArrowLeftRight, FileCheck2, FileText, Gift, Handshake, KeyRound, Landmark, type LucideIcon } from "lucide-react";
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
      className="flex min-h-32 flex-col gap-1 rounded-card border border-border bg-surface p-5 hover:border-border-strong hover:bg-hover-bg"
    >
      <Icon aria-hidden="true" className="mb-2 size-5 text-forest" strokeWidth={1.5} />
      <span className="font-heading text-lg font-semibold">{tRoot(workflow.subtype.labelKey)}</span>
      {(DESCRIPTION_KEYS as readonly string[]).includes(key) ? (
        <span className="text-sm text-muted-ink">{t(`workflowDescription.${key as DescriptionKey}`)}</span>
      ) : null}
      <span className="mt-auto pt-2 text-xs text-muted-ink">
        {form === null ? tWorkflow("noGazetteForm") : tWorkflow("gazetteForm", { number: form })}
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
    <section aria-labelledby="common-workflows-title">
      <SectionHeader id="common-workflows-title" title={t("commonWorkflowsTitle")} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {available.map((workflow) => (
          <WorkflowCard key={workflow.subtype.id} workflow={workflow} />
        ))}
      </div>
      {planned.length > 0 ? (
        <div className="mt-5 flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm text-muted-ink">
          <h3 className="font-medium">{t("comingSoon")}</h3>
          <ul className="flex flex-wrap gap-x-6 gap-y-1">
            {planned.map((workflow) => (
              <li key={workflow.subtype.id} className="cursor-default">
                {/* A planned instrument is a disabled link: announced as unavailable, never focusable. */}
                <span role="link" aria-disabled="true">
                  {tRoot(workflow.subtype.labelKey)}
                  {workflow.subtype.gazetteFormNumber !== null ? (
                    <span className="ml-2 text-xs">{tWorkflow("gazetteForm", { number: workflow.subtype.gazetteFormNumber })}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
