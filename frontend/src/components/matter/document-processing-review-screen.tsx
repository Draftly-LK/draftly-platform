"use client";

import { LoaderCircle } from "lucide-react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState, useRef } from "react";
import { ClassificationReviewScreen } from "@/components/matter/classification-review-screen";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { ApiError, isApiEnabled, apiErrorMessage } from "@/lib/api/client";
import {
  getDocumentReview,
  getPrivateDocumentArtifact,
} from "@/lib/api/documents";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiDetectedDocument, ApiDocumentReview } from "@/types/rta";
import { FactRegister } from "./fact-register";
import { DocumentDecisions, isDocumentDecided } from "./document-decisions";
import { ReviewNextStep } from "./review-next-step";
import { SourceFilePreview } from "./source-file-preview";
import { useSourceLabels } from "./use-source-labels";

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
  return (
    <DocumentProcessingReviewFlow
      key={`${props.matterId}:${props.documentId}`}
      {...props}
    />
  );
}

function DocumentProcessingReviewFlow({
  matterId,
  documentId,
}: {
  matterId: string;
  documentId: string;
}) {
  const t = useTranslations("documentProcessingReview");
  const evidenceT = useTranslations("factRegister");
  const operations = useTranslations("documentOperations");
  const getToken = useTokenProvider();
  const [review, setReview] = useState<ApiDocumentReview | null>(null);
  const [legacy, setLegacy] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [ocr, setOcr] = useState<OcrPayload | null>(null);
  const [ocrUnavailable, setOcrUnavailable] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<ApiDetectedDocument | null>(null);
  const reviewGeneration = useRef({ value: 0 });
  const sourceLabels = useSourceLabels(
    getToken,
    review?.pages.map((page) => page.sourceFileId) ?? [],
    matterId,
  );

  useEffect(() => {
    let active = true;
    const epoch = reviewGeneration.current;
    getDocumentReview(getToken, documentId)
      .then((value) => {
        if (!active) return;
        if (
          value.matterId !== matterId ||
          value.detectedDocumentId !== documentId
        )
          throw new Error("Foreign document review");
        setReview(value);
        setLegacy(false);
        setPageIndex(0);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        if (
          cause instanceof ApiError &&
          cause.code === "document_review_not_found"
        )
          setLegacy(true);
        else setError(apiErrorMessage(cause, t("loadError")));
      });
    return () => {
      active = false;
      epoch.value++;
    };
  }, [documentId, matterId, getToken, t, document?.version]);

  const page = review?.pages[pageIndex];
  useEffect(() => {
    if (!page) return;
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setImageUrl(null);
    setOcr(null);
    setOcrUnavailable(false);
    setImageError(false);
    void getPrivateDocumentArtifact(getToken, page.imageUrl, controller.signal)
      .then((image) => {
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(image);
        setImageUrl(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setImageError(true);
      });
    void getPrivateDocumentArtifact(getToken, page.ocrUrl, controller.signal)
      .then(async (json) => {
        const parsed = JSON.parse(await json.text()) as OcrPayload;
        if (!Array.isArray(parsed.elements))
          throw new Error("Invalid OCR payload");
        if (!controller.signal.aborted) setOcr(parsed);
      })
      .catch(() => {
        if (!controller.signal.aborted) setOcrUnavailable(true);
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

  if (legacy)
    return (
      <ClassificationReviewScreen
        matterId={matterId}
        documentId={documentId}
        onChange={setDocument}
      />
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

  const pending = review.candidates.filter(
    (field) => field.reviewState !== "approved",
  ).length;
  const viewerCurrent =
    review.current === true &&
    (!document ||
      (document.versionRelationship !== "SUPERSEDED" &&
        document.interpretationGeneration === review.interpretationGeneration));

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
          <section className="min-w-0">
            <p role="status" className="text-amber-text mb-3 text-sm">
              {review.interpretationGeneration
                ? operations(viewerCurrent ? "currentView" : "historicalView", {
                    generation: review.interpretationGeneration,
                  })
                : operations("unknownView")}
            </p>
            <div className="mb-3 flex flex-wrap gap-2">
              {review.pages.map((item, index) => (
                <Button
                  key={item.id}
                  variant={index === pageIndex ? "primary" : "secondary"}
                  aria-pressed={index === pageIndex}
                  className="max-w-full whitespace-normal break-words text-left"
                  onClick={() => setPageIndex(index)}
                >
                  {item.sourceFileId && (
                    <>
                      {sourceLabels[item.sourceFileId] ??
                        operations("sourceReference", {
                          reference: item.sourceFileId,
                        })}{" "}
                      ·{" "}
                    </>
                  )}
                  {t("page", { page: item.pageNo })}
                </Button>
              ))}
            </div>

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
              ) : imageError ? (
                <p role="alert" className="text-red p-6 text-sm">
                  {t("artifactError")}
                </p>
              ) : (
                <div className="flex min-h-96 items-center justify-center">
                  <LoaderCircle className="size-6 animate-spin" />
                </div>
              )}
            </div>
            <p className="text-muted-ink mt-2 text-xs">{t("overlayNote")}</p>
            {ocrUnavailable && (
              <p role="status" className="text-muted-ink mt-2 text-xs">
                {evidenceT("ocrUnavailable")}
              </p>
            )}
            {!viewerCurrent && document && (
              <details className="border-border mt-4 space-y-3 border-t pt-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {operations("currentOriginals")}
                </summary>
                {document.fragments.map((fragment, index) => (
                  <SourceFilePreview
                    key={`${fragment.sourceFileId}:${index}`}
                    getToken={getToken}
                    matterId={matterId}
                    sourceFileId={fragment.sourceFileId}
                    pageStart={fragment.pageStart}
                    pageEnd={fragment.pageEnd}
                  />
                ))}
              </details>
            )}
          </section>
          <div className="min-w-0 space-y-6">
            <DocumentDecisions
              getToken={getToken}
              matterId={matterId}
              documentId={documentId}
              onChange={setDocument}
            />
            <FactRegister
              documentContext={document ?? undefined}
              sourceRevision={document?.version}
              matterId={matterId}
              documentId={documentId}
              onDecision={() => {
                const request = ++reviewGeneration.current.value;
                void getDocumentReview(getToken, documentId)
                  .then((value) => {
                    if (
                      request === reviewGeneration.current.value &&
                      value.matterId === matterId &&
                      value.detectedDocumentId === documentId
                    )
                      setReview(value);
                  })
                  .catch((cause) => {
                    if (request === reviewGeneration.current.value)
                      setError(apiErrorMessage(cause, t("loadError")));
                  });
              }}
            />
          </div>
        </div>
        <ReviewNextStep
          getToken={getToken}
          matterId={matterId}
          documentId={documentId}
          done={
            document !== null && isDocumentDecided(document) && pending === 0
          }
        />
      </div>
    </AppShell>
  );
}
