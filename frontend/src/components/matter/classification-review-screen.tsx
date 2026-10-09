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
import { FactRegister } from "./fact-register";

/**
 * Review when no logical extraction exists. The original fragments, document
 * decisions and canonical manual entries share the current interpretation.
 */
export function ClassificationReviewScreen({
  matterId,
  documentId,
  onChange,
}: {
  matterId: string;
  documentId: string;
  onChange?: (document: ApiDetectedDocument) => void;
}) {
  return isApiEnabled() ? (
    <ApiBoundClassificationReviewScreen
      matterId={matterId}
      documentId={documentId}
      onChange={onChange}
    />
  ) : (
    <ClassificationReviewUnavailable matterId={matterId} />
  );
}

function ApiBoundClassificationReviewScreen({
  matterId,
  documentId,
  onChange,
}: {
  matterId: string;
  documentId: string;
  onChange?: (document: ApiDetectedDocument) => void;
}) {
  const getToken = useTokenProvider();
  return (
    <ClassificationReviewFlow
      getToken={getToken}
      matterId={matterId}
      documentId={documentId}
      onChange={onChange}
    />
  );
}

function ClassificationReviewFlow({
  getToken,
  matterId,
  documentId,
  onChange,
}: {
  getToken: TokenProvider;
  matterId: string;
  documentId: string;
  onChange?: (document: ApiDetectedDocument) => void;
}) {
  const t = useTranslations("classificationReview");
  const [document, setDocument] = useState<ApiDetectedDocument | null>(null);

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-4 sm:p-6">
        {/* The document beside the decisions about it: nothing is classified blind. */}
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <section
            aria-label={t("previewSection")}
            className="min-w-0 space-y-4"
          >
            {document ? (
              document.fragments.map((fragment) => (
                <SourceFilePreview
                  key={fragment.id}
                  getToken={getToken}
                  matterId={matterId}
                  sourceFileId={fragment.sourceFileId}
                  pageStart={fragment.pageStart}
                  pageEnd={fragment.pageEnd}
                />
              ))
            ) : (
              <div className="border-border-strong bg-canvas rounded-card flex min-h-72 items-center justify-center border">
                <LoaderCircle
                  aria-label={t("loadingPreview")}
                  className="size-6 animate-spin"
                  strokeWidth={1.5}
                />
              </div>
            )}
          </section>
          <div className="min-w-0 space-y-6">
            <DocumentDecisions
              getToken={getToken}
              matterId={matterId}
              documentId={documentId}
              onChange={(value) => {
                setDocument(value);
                onChange?.(value);
              }}
            />
            {document && (
              <FactRegister
                matterId={matterId}
                documentId={documentId}
                documentContext={document}
                sourceRevision={document.version}
              />
            )}
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
          <AlertCircle className="text-amber-text size-5" strokeWidth={1.5} />
          <p className="mt-2 text-sm">{t("backendNotConfigured")}</p>
        </div>
      </div>
    </AppShell>
  );
}
