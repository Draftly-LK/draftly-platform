"use client";

import { ArrowLeft, ArrowRight, CircleCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { buttonClass } from "@/components/ui/button";
import type { TokenProvider } from "@/lib/api/client";
import { getDocumentInbox } from "@/lib/api/documents";
import { cn } from "@/lib/utils";
import { isDocumentDecided } from "./document-decisions";

/**
 * Where to go once a document is reviewed: the next document still waiting, or,
 * when none is, on to the verified facts. Until this one is done, only the way
 * back to the inbox is offered, so nobody skips a decision by accident.
 */
export function ReviewNextStep({
  getToken,
  matterId,
  documentId,
  done,
}: {
  getToken: TokenProvider;
  matterId: string;
  documentId: string;
  done: boolean;
}) {
  const t = useTranslations("classificationReview");
  const [nextId, setNextId] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    if (!done) return;
    let active = true;
    getDocumentInbox(getToken, matterId)
      .then((inbox) => {
        if (!active) return;
        const waiting = inbox.documents.filter((item) => item.id !== documentId && !isDocumentDecided(item));
        setNextId(waiting[0]?.id ?? null);
      })
      .catch(() => {
        if (active) setNextId(null);
      });
    return () => {
      active = false;
    };
  }, [documentId, done, getToken, matterId]);

  const back = (
    <Link href={`/matters/${matterId}/documents`} className={buttonClass("secondary")}>
      <ArrowLeft aria-hidden="true" className="size-4" strokeWidth={1.5} />
      {t("back")}
    </Link>
  );
  if (!done || nextId === undefined) return <div className="mt-6">{back}</div>;

  return (
    <section aria-live="polite" className="border-border bg-surface mt-6 flex flex-wrap items-center gap-4 rounded-card border p-4">
      <CircleCheck aria-hidden="true" className="text-teal size-6 shrink-0" strokeWidth={1.5} />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t("documentDone")}</p>
        <p className="text-muted-ink text-sm">{nextId ? t("nextDocumentHint") : t("allDocumentsHint")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {back}
        <Link
          href={nextId ? `/matters/${matterId}/documents/${nextId}/review` : `/matters/${matterId}/facts`}
          className={cn(buttonClass("primary"))}
        >
          {nextId ? t("nextDocument") : t("goToFacts")}
          <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.5} />
        </Link>
      </div>
    </section>
  );
}
