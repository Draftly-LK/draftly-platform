"use client";

import { AlertCircle, CheckCircle2, ChevronRight, File, FileWarning, LoaderCircle, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button, buttonClass } from "@/components/ui/button";
import { isApiEnabled, type TokenProvider, apiErrorMessage } from "@/lib/api/client";
import { getDocumentInbox, uploadSourceFile } from "@/lib/api/documents";
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
  /** Bumped after an upload so the inbox reloads in place, without the full-page spinner. */
  const [refresh, setRefresh] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (refresh === 0) setLoading(true);
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
  }, [getToken, matterId, refresh, t]);

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

  const upload = (
    <UploadDocuments
      getToken={getToken}
      matterId={matterId}
      // The process prompt is the next step once files are waiting, so the upload steps back to secondary.
      primary={inbox.unprocessedSourceFileIds.length === 0}
      onStatus={setUploadStatus}
      onUploaded={() => setRefresh((value) => value + 1)}
    />
  );

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} action={upload} />
      <div className="p-6">
        <p className="text-muted-ink -mt-2 mb-4 text-xs">{t("uploadHint")}</p>
        <div aria-live="polite">
          {uploadStatus ? (
            <p
              role={uploadStatus.tone === "error" ? "alert" : undefined}
              className={`mb-4 flex items-start gap-2 rounded-card border p-3 text-sm ${uploadStatus.tone === "error" ? "border-red bg-red-bg text-red" : "border-border bg-surface"}`}
            >
              {uploadStatus.tone === "busy" ? (
                <LoaderCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0 animate-spin" strokeWidth={1.5} />
              ) : uploadStatus.tone === "error" ? (
                <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={1.5} />
              ) : (
                <CheckCircle2 aria-hidden="true" className="text-teal mt-0.5 size-4 shrink-0" strokeWidth={1.5} />
              )}
              <span>{uploadStatus.text}</span>
            </p>
          ) : null}
        </div>
        {inbox.sourceFiles.length === 0 ? (
          <div className="border-border bg-surface mb-6 rounded-card border p-6 text-center">
            <Upload aria-hidden="true" className="text-forest mx-auto size-6" strokeWidth={1.5} />
            <p className="mt-2 font-medium">{t("emptyFiles")}</p>
          </div>
        ) : null}
        {/* Summary bar */}
        <div className="border-border bg-surface mb-6 grid grid-cols-2 gap-4 rounded-card border p-4 text-center sm:grid-cols-3 lg:grid-cols-5">
          <div>
            <p className="text-muted-ink text-xs font-semibold">
              {t("totalDocuments", { count: inbox.documents.length })}
            </p>
            <p className="text-2xl font-semibold">{inbox.documents.length}</p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold">
              {t("boundaryReview", { count: inbox.boundaryReviewDocumentIds.length })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.boundaryReviewDocumentIds.length}
            </p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold">
              {t("classificationReview", {
                count: inbox.classificationReviewDocumentIds.length,
              })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.classificationReviewDocumentIds.length}
            </p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold">
              {t("unidentified", { count: inbox.unidentifiedDocumentIds.length })}
            </p>
            <p className="text-2xl font-semibold">
              {inbox.unidentifiedDocumentIds.length}
            </p>
          </div>
          <div>
            <p className="text-muted-ink text-xs font-semibold">
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
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="font-medium">
                  {t("waitingToProcess", { count: inbox.unprocessedSourceFileIds.length })}
                </p>
                <p className="text-muted-ink text-sm">{t("waitingToProcessBody")}</p>
              </div>
              <Link href={`/matters/${matterId}/processing`} className={buttonClass("primary")}>
                {tProcessing("readyToProcess")}
                <ChevronRight className="size-4" strokeWidth={1.5} />
              </Link>
            </div>
          </div>
        )}

        {/* Detected documents table */}
        {inbox.documents.length > 0 && (
          <section className="mb-8">
            <h2 className="text-muted-ink mb-3 text-xs font-semibold">
              {t("documentTable")}
            </h2>
            <div className="border-border bg-surface overflow-hidden rounded-card border">
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
            <h2 className="text-muted-ink mb-3 text-xs font-semibold">
              {t("sourceFilesSection")}
            </h2>
            <div className="border-border bg-surface overflow-hidden rounded-card border">
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

interface UploadStatus {
  tone: "busy" | "done" | "error";
  text: string;
}

/**
 * Adds files to an existing matter, the same call the new-matter wizard makes
 * (`POST /matters/{id}/source-files`), one file at a time. Uploading only
 * stores the file; reading it is the separate processing step.
 */
function UploadDocuments({
  getToken,
  matterId,
  primary,
  onStatus,
  onUploaded,
}: {
  getToken: TokenProvider;
  matterId: string;
  primary: boolean;
  onStatus: (status: UploadStatus) => void;
  onUploaded: () => void;
}) {
  const t = useTranslations("documents");
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function upload(files: File[]) {
    if (files.length === 0) return;
    setBusy(true);
    onStatus({ tone: "busy", text: t("uploading", { count: files.length }) });
    let failed = 0;
    let reason: string | null = null;
    for (const file of files) {
      try {
        await uploadSourceFile(getToken, matterId, file);
      } catch (cause: unknown) {
        failed += 1;
        reason = apiErrorMessage(cause, t("uploadFailed"));
      }
    }
    setBusy(false);
    const added = files.length - failed;
    onStatus(
      failed === 0
        ? { tone: "done", text: t("uploadDone", { count: added }) }
        : { tone: "error", text: `${t("uploadSomeFailed", { count: failed })} ${reason ?? ""}`.trim() },
    );
    if (added > 0) onUploaded();
  }

  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept="application/pdf,image/*"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          // Clear it so choosing the same file again still fires a change.
          event.target.value = "";
          void upload(files);
        }}
      />
      <Button
        type="button"
        variant={primary ? "primary" : "secondary"}
        disabled={busy}
        aria-busy={busy || undefined}
        onClick={() => input.current?.click()}
      >
        {busy ? (
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" strokeWidth={1.5} />
        ) : (
          <Upload aria-hidden="true" className="size-4" strokeWidth={1.5} />
        )}
        {t("upload")}
      </Button>
    </>
  );
}

function DocumentsUnavailable({ matterId }: { matterId: string }) {
  const t = useTranslations("documents");
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
