"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  LoaderCircle,
  Save,
} from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import { useEffect, useMemo, useState } from "react";
import { ClassificationReviewScreen } from "@/components/matter/classification-review-screen";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { ApiError, isApiEnabled, apiErrorMessage } from "@/lib/api/client";
import {
  approveReviewCandidate,
  editReviewCandidate,
  getDocumentReview,
  getPrivateDocumentArtifact,
} from "@/lib/api/documents";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiDocumentReview, ApiReviewCandidate } from "@/types/rta";

interface OcrPoint {
  x: number;
  y: number;
}
interface OcrElement {
  level: string;
  correctedPolygon: OcrPoint[];
}
interface OcrPayload {
  elements: OcrElement[];
}

export function DocumentProcessingReviewScreen(props: {
  matterId: string;
  documentId: string;
}) {
  if (!isApiEnabled()) return <ClassificationReviewScreen {...props} />;
  return <DocumentProcessingReviewFlow {...props} />;
}

function DocumentProcessingReviewFlow({
  matterId,
  documentId,
}: {
  matterId: string;
  documentId: string;
}) {
  const t = useTranslations("documentProcessingReview");
  const getToken = useTokenProvider();
  const [review, setReview] = useState<ApiDocumentReview | null>(null);
  const [legacy, setLegacy] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [ocr, setOcr] = useState<OcrPayload | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getDocumentReview(getToken, documentId)
      .then((value) => {
        if (!active) return;
        setReview(value);
        setEdits(
          Object.fromEntries(
            value.candidates.map((field) => [
              field.id,
              field.editedValue ?? field.candidateValue,
            ]),
          ),
        );
      })
      .catch((cause: unknown) => {
        if (!active) return;
        if (
          cause instanceof ApiError &&
          cause.code === "document_review_not_found"
        )
          setLegacy(true);
        else
          setError(apiErrorMessage(cause, t("loadError")));
      });
    return () => {
      active = false;
    };
  }, [documentId, getToken, t]);

  const page = review?.pages[pageIndex];
  useEffect(() => {
    if (!page) return;
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setImageUrl(null);
    setOcr(null);
    Promise.all([
      getPrivateDocumentArtifact(getToken, page.imageUrl, controller.signal),
      getPrivateDocumentArtifact(getToken, page.ocrUrl, controller.signal),
    ])
      .then(async ([image, json]) => {
        objectUrl = URL.createObjectURL(image);
        setImageUrl(objectUrl);
        setOcr(JSON.parse(await json.text()) as OcrPayload);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(
            apiErrorMessage(cause, t("artifactError")),
          );
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [getToken, page, t]);

  const words = useMemo(
    () => ocr?.elements.filter((element) => element.level === "word") ?? [],
    [ocr],
  );
  const updateCandidate = (saved: ApiReviewCandidate) => {
    setReview((current) =>
      current
        ? {
            ...current,
            candidates: current.candidates.map((item) =>
              item.id === saved.id ? saved : item,
            ),
          }
        : current,
    );
    setEdits((current) => ({
      ...current,
      [saved.id]: saved.editedValue ?? saved.candidateValue,
    }));
  };
  const save = async (field: ApiReviewCandidate) => {
    setBusy(field.id);
    setError(null);
    try {
      updateCandidate(
        await editReviewCandidate(
          getToken,
          field.id,
          edits[field.id] ?? "",
          field.version,
        ),
      );
    } catch (cause) {
      setError(apiErrorMessage(cause, t("saveError")));
    } finally {
      setBusy(null);
    }
  };
  const approve = async (field: ApiReviewCandidate) => {
    setBusy(field.id);
    setError(null);
    try {
      updateCandidate(
        await approveReviewCandidate(getToken, field.id, field.version),
      );
    } catch (cause) {
      setError(apiErrorMessage(cause, t("approveError")));
    } finally {
      setBusy(null);
    }
  };

  if (legacy)
    return (
      <ClassificationReviewScreen matterId={matterId} documentId={documentId} />
    );
  if (!review)
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="flex justify-center p-12">
          {error ?? <LoaderCircle className="size-6 animate-spin" />}
        </div>
      </AppShell>
    );

  const warnings = page
    ? [
        page.rotationStatus === "rotation_uncertain"
          ? t("rotationWarning")
          : null,
        page.qualityStatus !== "normal"
          ? t(`quality.${page.qualityStatus}`)
          : null,
        page.classificationConfidence < 0.55
          ? t("classificationWarning")
          : null,
      ].filter(Boolean)
    : [];

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        {error && (
          <div className="border-red bg-red-bg text-red mb-4 rounded border p-3">
            {error}
          </div>
        )}
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <section>
            <div className="mb-3 flex flex-wrap gap-2">
              {review.pages.map((item, index) => (
                <Button
                  key={item.id}
                  variant={index === pageIndex ? "primary" : "secondary"}
                  onClick={() => setPageIndex(index)}
                >
                  {t("page", { page: item.pageNo })}
                </Button>
              ))}
            </div>
            {warnings.length > 0 && (
              <div className="border-amber bg-amber-bg text-amber-text mb-3 rounded border p-3">
                {warnings.map((warning) => (
                  <p key={warning}>
                    <AlertTriangle className="mr-2 inline size-4" />
                    {warning}
                  </p>
                ))}
              </div>
            )}
            <div className="border-border-strong bg-canvas relative overflow-hidden rounded border">
              {imageUrl ? (
                <>
                  <Image
                    src={imageUrl}
                    alt={t("pageAlt", { page: page?.pageNo ?? 1 })}
                    width={page?.correctedWidth ?? 1}
                    height={page?.correctedHeight ?? 1}
                    unoptimized
                    className="block h-auto w-full"
                  />
                  <svg
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-0 size-full"
                    viewBox="0 0 1 1"
                    preserveAspectRatio="none"
                  >
                    {words.map((word, index) => (
                      <polygon
                        key={index}
                        points={word.correctedPolygon
                          .map((point) => `${point.x},${point.y}`)
                          .join(" ")}
                        fill="rgba(37,99,235,.08)"
                        stroke="rgba(37,99,235,.65)"
                        strokeWidth="0.0015"
                      />
                    ))}
                  </svg>
                </>
              ) : (
                <div className="flex min-h-96 items-center justify-center">
                  <LoaderCircle className="size-6 animate-spin" />
                </div>
              )}
            </div>
            <p className="text-muted-ink mt-2 text-xs">{t("overlayNote")}</p>
          </section>
          <section className="border-border bg-surface rounded-card border p-4 shadow-card">
            <h2 className="font-semibold">{t("fieldsTitle")}</h2>
            <p className="text-muted-ink mb-4 text-sm">
              {t("fieldsDescription")}
            </p>
            <div className="space-y-4">
              {review.candidates.map((field) => (
                <div key={field.id}>
                  <label className="text-sm font-medium">
                    {humanizeMessageKey(field.key)}
                    <input
                      className="border-border-strong mt-1 w-full rounded-control border px-3 py-2"
                      value={edits[field.id] ?? ""}
                      onChange={(event) =>
                        setEdits((current) => ({
                          ...current,
                          [field.id]: event.target.value,
                        }))
                      }
                      disabled={
                        busy === field.id || field.reviewState === "approved"
                      }
                    />
                  </label>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-muted-ink text-xs">
                      {field.reviewState === "approved"
                        ? t("approved")
                        : t("unverified")}
                    </span>
                    <Button
                      onClick={() => void save(field)}
                      disabled={
                        busy === field.id || field.reviewState === "approved"
                      }
                    >
                      <Save className="size-4" />
                      {t("save")}
                    </Button>
                    <Button
                      variant="primary"
                      onClick={() => void approve(field)}
                      disabled={
                        busy === field.id || field.reviewState === "approved"
                      }
                    >
                      <Check className="size-4" />
                      {t("approve")}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
        <Link
          className="mt-6 inline-flex"
          href={`/matters/${matterId}/documents`}
        >
          <Button>
            <ArrowLeft className="size-4" />
            {t("back")}
          </Button>
        </Link>
      </div>
    </AppShell>
  );
}
