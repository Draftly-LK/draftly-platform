"use client";

import { AlertCircle, ChevronRight, File, FileWarning, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { isApiEnabled, type TokenProvider, apiErrorMessage } from "@/lib/api/client";
import { getDocumentInbox } from "@/lib/api/documents";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiDocumentInbox } from "@/types/rta";

/**
 * Screen 6: Document Inbox — REBUILD
 *
 * Fetch and display the document inbox: source files, detected documents,
 * and which ones need review (classification/boundary).
 */
export function DocumentsScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundDocumentsScreen matterId={matterId} />
  ) : (
    <DocumentsUnavailable matterId={matterId} />
  );
}

function ApiBoundDocumentsScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  return <DocumentsFlow getToken={getToken} matterId={matterId} />;
}

function DocumentsFlow({
  getToken,
  matterId,
}: {
  getToken: TokenProvider;
  matterId: string;
}) {
  const t = useTranslations("documents");
  const tProcessing = useTranslations("processing");
  const fileStateLabel = useEnumLabel("enums.sourceFileState");
  const boundaryLabel = useEnumLabel("enums.boundaryStatus");
  const classLabel = (id: string) => humanizeMessageKey(id.split(".").pop() ?? id);
  const [inbox, setInbox] = useState<ApiDocumentInbox | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getDocumentInbox(getToken, matterId)
      .then((result) => {
        if (!cancelled) setInbox(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(apiErrorMessage(cause, t("loadError")));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="flex items-center justify-center py-12">
          <LoaderCircle className="size-6 animate-spin" strokeWidth={1.5} />
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="p-6">
          <div className="border-red bg-red-bg text-red rounded border p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} />
              <p className="text-sm">{error}</p>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!inbox) return null;

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        {/* Summary bar */}
        <div className="border-border bg-surface mb-6 flex flex-wrap gap-4 rounded-card border p-4 shadow-card">
          <div>
            <p className="text-muted-ink text-xs font-semibold uppercase">
              {t("totalDocuments", { count: inbox.documents.length })}
            </p>
            <p className="text-2xl font-semibold">{inbox.documents.length}</p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold uppercase">
              {t("boundaryReview", { count: inbox.boundaryReviewDocumentIds.length })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.boundaryReviewDocumentIds.length}
            </p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold uppercase">
              {t("classificationReview", {
                count: inbox.classificationReviewDocumentIds.length,
              })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.classificationReviewDocumentIds.length}
            </p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold uppercase">
              {t("unidentified", { count: inbox.unidentifiedDocumentIds.length })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.unidentifiedDocumentIds.length}
            </p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold uppercase">
              {t("unprocessed", { count: inbox.unprocessedSourceFileIds.length })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.unprocessedSourceFileIds.length}
            </p>
          </div>
        </div>

        {/* Unprocessed files prompt */}
        {inbox.unprocessedSourceFileIds.length > 0 && (
          <div className="border-border-strong bg-selected-bg mb-6 rounded border p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium">
                  {inbox.unprocessedSourceFileIds.length} files waiting to be processed
                </p>
                <p className="text-muted-ink text-sm">
                  Run the extraction pipeline before classifying documents.
                </p>
              </div>
              <Link href={`/matters/${matterId}/processing`}>
                <Button variant="primary">
                  {tProcessing("readyToProcess")}
                  <ChevronRight className="size-4" strokeWidth={1.5} />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Detected documents table */}
        {inbox.documents.length > 0 && (
          <section className="mb-8">
            <h2 className="text-muted-ink mb-3 text-xs font-semibold uppercase">
              {t("documentTable")}
            </h2>
            <div className="border-border bg-surface overflow-hidden rounded-card border shadow-card">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px] border-collapse text-left">
                  <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
                    <tr className="border-border h-10 border-b">
                      <th className="px-3">{t("documentId")}</th>
                      <th className="px-3">{t("classification")}</th>
                      <th className="px-3">{t("boundary")}</th>
                      <th className="px-3">{t("pages")}</th>
                      <th className="px-3">{t("multipleSource")}</th>
                      <th className="px-3">{t("actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inbox.documents.map((doc) => {
                      const needsClassification =
                        inbox.classificationReviewDocumentIds.includes(doc.id);
                      const needsBoundary = inbox.boundaryReviewDocumentIds.includes(
                        doc.id
                      );
                      const needsReview = needsClassification || needsBoundary;

                      return (
                        <tr
                          key={doc.id}
                          className={`border-border h-11 border-b last:border-b-0 ${needsReview ? "hover:bg-hover-bg" : ""}`}
                        >
                          <td className="px-3">
                            <span className="flex items-center gap-2">
                              <File className="size-4 shrink-0" strokeWidth={1.5} />
                              <span className="text-sm">{doc.id.slice(0, 8)}</span>
                            </span>
                          </td>
                          <td className="px-3">
                            <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-border-strong bg-surface px-2 py-1 text-xs font-semibold">
                              {doc.classId
                                ? classLabel(doc.classId)
                                : t("unidentifiedClass")}
                            </span>
                          </td>
                          <td className="px-3">
                            <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-border-strong bg-surface px-2 py-1 text-xs font-semibold">
                              {boundaryLabel(doc.boundaryStatus)}
                            </span>
                          </td>
                          <td className="px-3 text-sm">
                            {doc.fragments.length}
                          </td>
                          <td className="px-3 text-sm">
                            {doc.spansMultipleSources ? t("yes") : t("no")}
                          </td>
                          <td className="px-3">
                            {needsReview ? (
                              <Link
                                href={`/matters/${matterId}/documents/${doc.id}/review`}
                              >
                                <Button>
                                  {t("reviewAction")}
                                  <ChevronRight className="size-4" strokeWidth={1.5} />
                                </Button>
                              </Link>
                            ) : (
                              <span className="text-muted-ink text-sm">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* Source files section */}
        {inbox.sourceFiles.length > 0 && (
          <section>
            <h2 className="text-muted-ink mb-3 text-xs font-semibold uppercase">
              {t("sourceFilesSection")}
            </h2>
            <div className="border-border bg-surface overflow-hidden rounded-card border shadow-card">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[600px] border-collapse text-left text-sm">
                  <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
                    <tr className="border-border h-10 border-b">
                      <th className="px-3">{t("sourceFileName")}</th>
                      <th className="px-3">{t("sourceFileState")}</th>
                      <th className="px-3">{t("pages")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inbox.sourceFiles.map((file) => (
                      <tr
                        key={file.id}
                        className="border-border h-11 border-b last:border-b-0"
                      >
                        <td className="px-3">
                          <span className="flex items-center gap-2">
                            {file.state === "PROCESSING_FAILED" ? (
                              <FileWarning className="size-4 shrink-0" strokeWidth={1.5} />
                            ) : (
                              <File className="size-4 shrink-0" strokeWidth={1.5} />
                            )}
                            <span>{file.originalFilename}</span>
                          </span>
                        </td>
                        <td className="px-3">
                          <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-border-strong bg-surface px-2 py-1 text-xs font-semibold">
                            {fileStateLabel(file.state)}
                          </span>
                        </td>
                        <td className="px-3">
                          {file.pageCount || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}

function DocumentsUnavailable({ matterId }: { matterId: string }) {
  const t = useTranslations("documents");
  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border bg-surface rounded-card border p-6 shadow-card">
          <AlertCircle className="size-5 text-amber-text" strokeWidth={1.5} />
          <p className="mt-2 text-sm">{t("backendNotConfigured")}</p>
        </div>
      </div>
    </AppShell>
  );
}
