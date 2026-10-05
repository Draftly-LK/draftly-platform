"use client";

import { MessageSquareText } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { buttonClass } from "@/components/ui/button";
import { WorkflowCard, useCommonWorkflows } from "./common-workflows";

/**
 * Shown instead of the counts and the list when there are no matters yet. A
 * plain section, not a Card: the workflow cards inside it are the containers.
 */
export function FirstRunPanel() {
  const t = useTranslations("home");
  const { available } = useCommonWorkflows();
  return (
    <section aria-labelledby="first-run-title">
      <h2 id="first-run-title" className="text-xl font-semibold">
        {t("firstRunTitle")}
      </h2>
      <p className="mt-1 max-w-prose text-sm text-muted-ink">{t("firstRunBody")}</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {available.map((workflow) => (
          <WorkflowCard key={workflow.subtype.id} workflow={workflow} />
        ))}
      </div>
      <Link href="/assistant" className={`${buttonClass("secondary")} mt-5`}>
        <MessageSquareText aria-hidden="true" className="size-4" strokeWidth={1.5} />
        {t("askTitle")}
      </Link>
    </section>
  );
}
