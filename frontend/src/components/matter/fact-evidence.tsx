"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { AlertTriangle, FileCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getDocumentReview,
  getPrivateDocumentArtifact,
} from "@/lib/api/documents";
import type { TokenProvider } from "@/lib/api/client";
import type {
  ApiDetectedDocument,
  ApiFactEvidence,
  ApiFactEvidenceInput,
  ApiSourceFile,
} from "@/types/rta";
import { controlClass, RegisterError } from "./fact-register-common";

export function EvidenceSelector({
  sources,
  value,
  onChange,
  documentContext,
}: {
  sources: ApiSourceFile[];
  value: ApiFactEvidenceInput | undefined;
  onChange: (value: ApiFactEvidenceInput | undefined) => void;
  documentContext?: ApiDetectedDocument;
}) {
  const t = useTranslations("factRegister");
  const operations = useTranslations("documentOperations");
  const source = sources.find((s) => s.id === value?.sourceFileId);
  const belongs = (item: ApiFactEvidenceInput) =>
    Boolean(
      documentContext?.interpretationGeneration &&
        documentContext.versionRelationship !== "SUPERSEDED" &&
        documentContext.fragments.some(
          (fragment) =>
            fragment.sourceFileId === item.sourceFileId &&
            fragment.pageStart <= item.pageNumber &&
            fragment.pageEnd >= item.pageNumber,
        ),
    );
  const pin = (item: ApiFactEvidenceInput): ApiFactEvidenceInput =>
    belongs(item)
      ? {
          ...item,
          detectedDocumentId: documentContext!.id,
          interpretationGeneration: documentContext!.interpretationGeneration,
        }
      : item;
  const stale = Boolean(
    value?.detectedDocumentId &&
      documentContext &&
      value.detectedDocumentId === documentContext.id &&
      (!belongs(value) ||
        value.interpretationGeneration !==
          documentContext.interpretationGeneration),
  );
  return (
    <div className="grid min-w-0 gap-3 sm:grid-cols-2">
      <label className="text-sm font-medium">
        {t("evidenceSource")}
        <select
          className={controlClass}
          value={source?.id ?? ""}
          onChange={(e) => {
            const source = sources.find((s) => s.id === e.target.value);
            onChange(
              source
                ? pin({
                    sourceFileId: source.id,
                    sourceSha256: source.sha256,
                    pageNumber: 1,
                  })
                : undefined,
            );
          }}
        >
          <option value="">{t("noEvidenceSelected")}</option>
          {sources
            .filter(
              (s) =>
                s.pageCount && !["REJECTED", "SUPERSEDED"].includes(s.state),
            )
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.originalFilename}
              </option>
            ))}
        </select>
      </label>
      {source && value && (
        <label className="text-sm font-medium">
          {t("evidencePage")}
          <input
            type="number"
            min={1}
            max={source.pageCount ?? undefined}
            className={controlClass}
            value={value.pageNumber}
            onChange={(e) =>
              onChange(
                documentContext
                  ? pin({
                      sourceFileId: value.sourceFileId,
                      sourceSha256: value.sourceSha256,
                      pageNumber: Number(e.target.value),
                      snippet: value.snippet,
                    })
                  : { ...value, pageNumber: Number(e.target.value) },
              )
            }
          />
        </label>
      )}
      {value && (
        <label className="text-sm font-medium sm:col-span-2">
          {t("evidenceExcerpt")}
          <textarea
            className={controlClass}
            maxLength={2000}
            value={value.snippet ?? ""}
            onChange={(e) => onChange({ ...value, snippet: e.target.value })}
          />
          <span className="text-muted-ink text-xs font-normal">
            {t("excerptValidation")}
          </span>
        </label>
      )}
      {value?.detectedDocumentId && (
        <div className="space-y-2 text-sm sm:col-span-2">
          <p
            role="status"
            className={`flex items-start gap-2 ${stale ? "text-amber-text" : "text-muted-ink"}`}
          >
            {stale ? (
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <FileCheck className="size-4 shrink-0" aria-hidden="true" />
            )}
            {stale
              ? operations("evidenceChanged")
              : operations("evidenceGeneration", {
                  generation: value.interpretationGeneration ?? 1,
                })}
          </p>
          {stale && belongs(value) && (
            <Button
              size="sm"
              onClick={() =>
                onChange(
                  pin({
                    sourceFileId: value.sourceFileId,
                    sourceSha256: value.sourceSha256,
                    pageNumber: value.pageNumber,
                    snippet: value.snippet,
                  }),
                )
              }
            >
              {operations("renewEvidence")}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function FactEvidence({
  matterId,
  evidence,
  sources,
  getToken,
}: {
  matterId: string;
  evidence: ApiFactEvidence;
  sources: ApiSourceFile[];
  getToken: TokenProvider;
}) {
  const t = useTranslations("factRegister");
  const [artifact, setArtifact] = useState<{
    url: string;
    kind: "image" | "original";
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const generation = useRef({ value: 0 });
  const source = sources.find((s) => s.id === evidence.sourceFileId);
  useEffect(() => {
    const epoch = generation.current;
    return () => {
      epoch.value++;
    };
  }, []);
  useEffect(
    () => () => {
      if (artifact) URL.revokeObjectURL(artifact.url);
    },
    [artifact],
  );
  async function open(kind: "image" | "original") {
    const run = ++generation.current.value;
    setBusy(true);
    setError(null);
    setArtifact(null);
    try {
      let path = `/api/v1/source-files/${encodeURIComponent(evidence.sourceFileId)}/content`;
      if (kind === "image") {
        if (!evidence.detectedDocumentId)
          throw new Error("Page locator unavailable");
        const review = await getDocumentReview(
          getToken,
          evidence.detectedDocumentId,
          evidence.interpretationGeneration ?? 1,
        );
        if (
          review.matterId !== matterId ||
          review.detectedDocumentId !== evidence.detectedDocumentId
        )
          throw new Error("Foreign review");
        const page = review.pages.find(
          (p) =>
            p.pageNo === evidence.pageNumber &&
            (p.sourceFileId === evidence.sourceFileId ||
              (!p.sourceFileId && !evidence.interpretationGeneration)),
        );
        if (!page) throw new Error("Page unavailable");
        path = page.imageUrl;
      }
      const blob = await getPrivateDocumentArtifact(getToken, path);
      if (run === generation.current.value)
        setArtifact({ url: URL.createObjectURL(blob), kind });
    } catch (cause) {
      if (run === generation.current.value) setError(cause);
    } finally {
      if (run === generation.current.value) setBusy(false);
    }
  }
  return (
    <section className="border-border bg-surface min-w-0 space-y-2 rounded border p-3">
      <h4 className="break-words text-sm font-semibold">
        {source?.originalFilename ?? t("sourceUnavailable")} ·{" "}
        {t("pageNumber", { number: evidence.pageNumber })}
      </h4>
      <p className="text-muted-ink text-xs">
        {t(
          evidence.precision === "text" && evidence.supportingText
            ? "textPrecision"
            : "pagePrecision",
        )}
      </p>
      {evidence.supportingText && (
        <blockquote className="border-teal whitespace-pre-wrap break-words border-l-2 pl-3 text-sm">
          {evidence.supportingText}
        </blockquote>
      )}
      {evidence.pageText ? (
        <details>
          <summary className="text-teal cursor-pointer text-sm">
            {t("storedPageText")}
          </summary>
          <p className="mt-2 whitespace-pre-wrap break-words text-sm">
            {evidence.pageText}
          </p>
        </details>
      ) : (
        <p className="text-muted-ink text-sm">{t("ocrUnavailable")}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => void open("original")}>
          {t("openOriginal")}
        </Button>
        {evidence.detectedDocumentId && (
          <Button disabled={busy} onClick={() => void open("image")}>
            {t("openPage")}
          </Button>
        )}
        {evidence.detectedDocumentId && (
          <Link
            className="text-teal self-center text-sm underline"
            href={`/matters/${encodeURIComponent(matterId)}/documents/${encodeURIComponent(evidence.detectedDocumentId)}/review`}
          >
            {t("reviewDocument")}
          </Link>
        )}
      </div>
      {error != null && <RegisterError cause={error} />}
      {artifact?.kind === "original" && (
        <a
          className="text-teal inline-block text-sm underline"
          href={artifact.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("viewLoadedOriginal")}
        </a>
      )}
      {artifact?.kind === "image" && (
        <div>
          {/* Authenticated blob URL, never a remote tracking image. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={artifact.url}
            alt={t("sourcePageAlt", { number: evidence.pageNumber })}
            className="h-auto max-w-full rounded"
          />
        </div>
      )}
    </section>
  );
}
