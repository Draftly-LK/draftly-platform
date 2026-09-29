"use client";

import { AlertCircle, ArrowLeft, Check, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import {
  getDocumentInbox,
  recordBoundaryDecision,
  recordClassificationDecision,
} from "@/lib/api/documents";
import { getRtaDocumentClasses } from "@/lib/api/rta";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiDetectedDocument } from "@/types/rta";
import type { ApiRtaDocumentClass } from "@/lib/api/rta";

/**
 * Screen 7: Classification Review — NEW
 *
 * Allow the lawyer to:
 * 1. Select a document class from the controlled catalogue
 * 2. Confirm the boundary (page ranges) as-is
 *
 * Note: There is no single "get one document" endpoint, so we fetch the
 * entire inbox and find the document by ID.
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
  const [classes, setClasses] = useState<ApiRtaDocumentClass[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch document and classes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      getDocumentInbox(getToken, matterId),
      getRtaDocumentClasses(getToken),
    ])
      .then(([inbox, classesContract]) => {
        if (!cancelled) {
          const doc = inbox.documents.find((d) => d.id === documentId);
          if (!doc) {
            setError("Document not found");
            return;
          }
          setDocument(doc);
          setClasses(classesContract.classes);
          setSelectedClassId(doc.classId || "");
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof ApiError ? cause.message : t("error"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, documentId, t]);

  const handleClassification = async () => {
    if (!document || !selectedClassId) return;

    setSaving(true);
    setError(null);

    try {
      const updated = await recordClassificationDecision(
        getToken,
        documentId,
        { classId: selectedClassId },
        document.version
      );
      setSuccessMessage(t("success"));
      // Update local state
      setDocument(updated);
    } catch (cause: unknown) {
      const message = cause instanceof ApiError ? cause.message : t("error");
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const handleBoundary = async () => {
    if (!document) return;

    setSaving(true);
    setError(null);

    try {
      const updated = await recordBoundaryDecision(
        getToken,
        documentId,
        {
          fragments: document.fragments.map((f) => ({
            sourceFileId: f.sourceFileId,
            pageStart: f.pageStart,
            pageEnd: f.pageEnd,
            orderInDocument: f.orderInDocument,
          })),
        },
        document.version
      );
      setSuccessMessage(t("boundarySuccess"));
      // Update local state
      setDocument(updated);
    } catch (cause: unknown) {
      const message = cause instanceof ApiError ? cause.message : t("error");
      setError(message);
    } finally {
      setSaving(false);
    }
  };

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

  if (error && !document) {
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

  if (!document) return null;

  const selectedClass = classes.find((c) => c.id === selectedClassId);

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        {error && (
          <div className="border-red bg-red-bg text-red mb-4 rounded border p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} />
              <p className="text-sm">{error}</p>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="border-forest bg-soft-green text-forest mb-4 rounded border p-4">
            <div className="flex items-start gap-2">
              <Check className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} />
              <p className="text-sm">{successMessage}</p>
            </div>
          </div>
        )}

        <div className="mx-auto max-w-2xl">
          {/* Document fragments display */}
          <section className="border-border bg-surface mb-6 rounded-card border p-4 shadow-card">
            <h2 className="mb-3 font-semibold">{t("documentFragments")}</h2>
            <ul className="divide-border divide-y">
              {document.fragments.map((fragment) => (
                <li key={fragment.id} className="py-2">
                  <p className="font-medium">
                    {t("pageRange", {
                      start: fragment.pageStart,
                      end: fragment.pageEnd,
                    })}
                  </p>
                  <p className="text-muted-ink text-sm">
                    {fragment.boundaryConfidence !== null
                      ? `${t("boundaryConfidence")}: ${(
                          fragment.boundaryConfidence * 100
                        ).toFixed(0)}%`
                      : t("boundaryConfidence") + ": Lawyer-confirmed"}
                  </p>
                </li>
              ))}
            </ul>
          </section>

          {/* Classification section */}
          <section className="border-border bg-surface mb-6 rounded-card border p-4 shadow-card">
            <h2 className="mb-3 font-semibold">{t("classificationStatus")}</h2>

            <div className="mb-4">
              <label className="block font-medium">
                {t("selectClass")}
                <select
                  value={selectedClassId}
                  onChange={(e) => setSelectedClassId(e.target.value)}
                  disabled={saving}
                  className="border-border-strong bg-surface mt-2 min-h-10 w-full rounded border px-3 py-2"
                >
                  <option value="">Choose a class...</option>
                  {classes.map((cls) => (
                    <option key={cls.id} value={cls.id}>
                      {cls.id.split(".").pop() || cls.id}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {selectedClass && (
              <div className="border-border-strong bg-canvas mb-4 rounded border p-3 text-sm">
                <p className="font-medium">{selectedClass.labelKey}</p>
                <p className="text-muted-ink mt-1">{selectedClass.descriptionKey}</p>
              </div>
            )}

            <Button
              disabled={!selectedClassId || saving}
              onClick={() => void handleClassification()}
              variant="primary"
            >
              {saving ? (
                <>
                  <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
                  Saving...
                </>
              ) : (
                <>
                  <Check className="size-4" strokeWidth={1.5} />
                  {t("classifyNow")}
                </>
              )}
            </Button>
          </section>

          {/* Boundary section */}
          {document.boundaryStatus !== "CONFIRMED" && (
            <section className="border-border bg-surface mb-6 rounded-card border p-4 shadow-card">
              <h2 className="mb-3 font-semibold">{t("boundaryActions")}</h2>
              <p className="text-muted-ink mb-4 text-sm">
                {t("confirmBoundary")}
              </p>
              <Button disabled={saving} onClick={() => void handleBoundary()}>
                {saving ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
                    Saving...
                  </>
                ) : (
                  <>
                    <Check className="size-4" strokeWidth={1.5} />
                    {t("confirmBoundaryNow")}
                  </>
                )}
              </Button>
            </section>
          )}

          {/* Navigation */}
          <div className="mt-8 flex gap-2">
            <Link href={`/matters/${matterId}/documents`}>
              <Button>
                <ArrowLeft className="size-4" strokeWidth={1.5} />
                {t("back")}
              </Button>
            </Link>
          </div>
        </div>
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
        <div className="border-border bg-surface rounded-card border p-6 shadow-card">
          <AlertCircle className="size-5 text-amber-text" strokeWidth={1.5} />
          <p className="mt-2 text-sm">Backend not configured.</p>
        </div>
      </div>
    </AppShell>
  );
}
