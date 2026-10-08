"use client";

import { AlertCircle, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiDetectedDocument } from "@/types/rta";
import { DocumentDecisions, isDocumentDecided } from "./document-decisions";
import { ReviewNextStep } from "./review-next-step";
import { SourceFilePreview } from "./source-file-preview";

/**
 * Screen 7: Classification Review — NEW
 *
 * The fallback when processing produced no page review (the legacy pipeline):
 * the original file is shown beside the two decisions, what the document is
 * and which pages it spans, and the next document is offered once it is done.
 *
 * Note: There is no single "get one document" endpoint, so the decisions fetch
 * the entire inbox and find the document by ID.
 */
export function ClassificationReviewScreen({
  matterId,
  documentId,
}: {
  matterId: string;
  documentId: string;
}) {
  return isApiEnabled() ? (
    <ApiBoundClassificationReviewScreen matterId={matterId} documentId={documentId} />
  ) : (
    <ClassificationReviewUnavailable matterId={matterId} />
  );
}

function ApiBoundClassificationReviewScreen({
  matterId,
  documentId,
}: {
  matterId: string;
  documentId: string;
}) {
  const getToken = useTokenProvider();
  return (
    <ClassificationReviewFlow
      getToken={getToken}
      matterId={matterId}
      documentId={documentId}
    />
  );
}

function ClassificationReviewFlow({
  getToken,
  matterId,
  documentId,
}: {
  getToken: TokenProvider;
  matterId: string;
  documentId: string;
}) {
  const t = useTranslations("classificationReview");
  const [document, setDocument] = useState<ApiDetectedDocument | null>(null);

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-4 sm:p-6">
        {/* The document beside the decisions about it: nothing is classified blind. */}
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <section aria-label={t("previewSection")} className="min-w-0 space-y-4">
            {document ? (
              document.fragments.map((fragment) => (
                <SourceFilePreview
                  key={fragment.id}
                  getToken={getToken}
                  sourceFileId={fragment.sourceFileId}
                  pageStart={fragment.pageStart}
                  pageEnd={fragment.pageEnd}
                />
              ))
            ) : (
              <div className="border-border-strong bg-canvas flex min-h-72 items-center justify-center rounded-card border">
                <LoaderCircle aria-label={t("loadingPreview")} className="size-6 animate-spin" strokeWidth={1.5} />
              </div>
            )}
          </section>
          <div className="min-w-0">
            <DocumentDecisions getToken={getToken} matterId={matterId} documentId={documentId} onChange={setDocument} />
          </div>
        </div>
        <ReviewNextStep
          getToken={getToken}
          matterId={matterId}
          documentId={documentId}
          done={document !== null && isDocumentDecided(document)}
        />
      </div>
    </AppShell>
  );
}

function ClassificationReviewUnavailable({ matterId }: { matterId: string }) {
  const t = useTranslations("classificationReview");
  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border bg-surface rounded-card border p-6">
          <AlertCircle className="size-5 text-amber-text" strokeWidth={1.5} />
          <p className="mt-2 text-sm">{t("backendNotConfigured")}</p>
        </div>
      </div>
    </AppShell>
  );
}
