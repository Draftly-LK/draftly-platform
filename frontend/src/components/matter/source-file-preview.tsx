"use client";

import { FileWarning, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { apiErrorMessage, type TokenProvider } from "@/lib/api/client";
import { getPrivateDocumentArtifact } from "@/lib/api/documents";

/**
 * The original uploaded file, shown while a document is reviewed. The bytes are
 * fetched with the session token (never a public URL) and held as a local
 * object URL that is released when the preview goes away.
 */
export function SourceFilePreview({
  getToken,
  sourceFileId,
  pageStart,
  pageEnd,
}: {
  getToken: TokenProvider;
  sourceFileId: string;
  pageStart: number;
  pageEnd: number;
}) {
  const t = useTranslations("classificationReview");
  const [file, setFile] = useState<{ url: string; type: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setFile(null);
    setError(null);
    getPrivateDocumentArtifact(getToken, `/api/v1/source-files/${encodeURIComponent(sourceFileId)}/content`, controller.signal)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setFile({ url: objectUrl, type: blob.type });
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(apiErrorMessage(cause, t("previewError")));
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [getToken, sourceFileId, t]);

  const label = t("pageRange", { start: pageStart, end: pageEnd });
  return (
    <figure className="border-border-strong bg-canvas overflow-hidden rounded-card border">
      {error ? (
        <div role="alert" className="text-red flex min-h-72 flex-col items-center justify-center gap-2 p-6 text-sm">
          <FileWarning aria-hidden="true" className="size-6" strokeWidth={1.5} />
          {error}
        </div>
      ) : !file ? (
        <div className="flex min-h-72 items-center justify-center">
          <LoaderCircle aria-label={t("loadingPreview")} className="size-6 animate-spin" strokeWidth={1.5} />
        </div>
      ) : file.type === "application/pdf" ? (
        <iframe title={t("previewTitle", { pages: label })} src={`${file.url}#page=${pageStart}`} className="block h-[70vh] w-full bg-white" />
      ) : (
        // A local object URL of a private upload: next/image cannot optimise it, and must not try.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={file.url} alt={t("previewTitle", { pages: label })} className="block h-auto w-full bg-white" />
      )}
      <figcaption className="text-muted-ink border-border border-t px-3 py-2 text-xs">{label}</figcaption>
    </figure>
  );
}
