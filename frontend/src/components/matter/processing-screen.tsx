"use client";

import { AlertCircle, ChevronRight, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { listSourceFiles, processSourceFile } from "@/lib/api/documents";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiProcessingRun, ApiSourceFile } from "@/types/rta";

interface ProcessingEntry extends ApiSourceFile {
  isProcessing?: boolean;
  processingRun?: ApiProcessingRun;
}

/**
 * Screen 5: Processing — run the extraction pipeline over uploaded files.
 * The pipeline is synchronous; there is no polling. We add a client-side
 * visual delay so the screen doesn't feel instant/fake.
 */
export function ProcessingScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundProcessingScreen matterId={matterId} />
  ) : (
    <ProcessingUnavailable matterId={matterId} />
  );
}

function ApiBoundProcessingScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  return <ProcessingFlow getToken={getToken} matterId={matterId} />;
}

function ProcessingFlow({
  getToken,
  matterId,
}: {
  getToken: TokenProvider;
  matterId: string;
}) {
  const t = useTranslations("processing");
  const [sourceFiles, setSourceFiles] = useState<ProcessingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch source files on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listSourceFiles(getToken, matterId)
      .then((response) => {
        if (!cancelled) {
          setSourceFiles(response.items);
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
  }, [getToken, matterId, t]);

  const handleProcess = useCallback(
    async (file: ProcessingEntry) => {
      // Mark as processing in UI
      setSourceFiles((current) =>
        current.map((f) => (f.id === file.id ? { ...f, isProcessing: true } : f))
      );

      try {
        // Add a visual delay so the interaction doesn't feel instant
        const processingRunPromise = processSourceFile(getToken, file.id, file.version);
        await new Promise((resolve) => setTimeout(resolve, 1200));
        const run = await processingRunPromise;

        // Update with the result
        setSourceFiles((current) =>
          current.map((f) =>
            f.id === file.id
              ? { ...f, isProcessing: false, processingRun: run, state: run.sourceFileId ? "PROCESSED" : "PROCESSING_FAILED" }
              : f
          )
        );
      } catch (cause: unknown) {
        const message = cause instanceof ApiError ? cause.message : t("error");
        setError(message);
        setSourceFiles((current) =>
          current.map((f) =>
            f.id === file.id ? { ...f, isProcessing: false } : f
          )
        );
      }
    },
    [getToken, t]
  );

  const readyToProcess = sourceFiles.filter(
    (f) => f.state === "STORED" || f.state === "VALIDATED"
  );
  const alreadyProcessed = sourceFiles.filter(
    (f) =>
      f.state === "PROCESSED" ||
      f.state === "PROCESSING_FAILED" ||
      f.state === "REJECTED"
  );
  const canContinue = readyToProcess.length === 0;

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

  if (sourceFiles.length === 0) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="p-6">
          <div className="border-border bg-surface rounded-card border p-6 text-center shadow-card">
            <p className="text-muted-ink mb-4">{t("emptyState")}</p>
            <Link href={`/matters/${matterId}`}>
              <Button variant="primary">
                {t("continueToInbox")}
                <ChevronRight className="size-4" strokeWidth={1.5} />
              </Button>
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

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

        {readyToProcess.length > 0 && (
          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold">{t("readyToProcess")}</h2>
            <ul className="divide-border border-border divide-y border-y">
              {readyToProcess.map((file) => (
                <li
                  key={file.id}
                  className="flex min-h-14 items-center justify-between gap-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{file.originalFilename}</p>
                    <p className="text-muted-ink text-sm">
                      {file.pageCount ? `${file.pageCount} pages` : ""}
                    </p>
                  </div>
                  {file.isProcessing ? (
                    <div className="flex items-center gap-2">
                      <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
                      <span className="text-sm font-medium">{t("processing")}</span>
                    </div>
                  ) : (
                    <Button
                      disabled={file.isProcessing}
                      onClick={() => void handleProcess(file)}
                    >
                      {t("process")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {alreadyProcessed.length > 0 && (
          <section>
            <h2 className="mb-3 text-lg font-semibold">{t("alreadyProcessed")}</h2>
            <ul className="divide-border border-border divide-y border-y">
              {alreadyProcessed.map((file) => (
                <li
                  key={file.id}
                  className="flex min-h-14 items-center justify-between gap-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{file.originalFilename}</p>
                    <p className="text-muted-ink text-sm">
                      {file.pageCount ? `${file.pageCount} pages` : ""}
                    </p>
                  </div>
                  <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-border-strong bg-surface px-2 py-1 text-xs font-semibold">
                    {file.state === "PROCESSED"
                      ? t("succeeded")
                      : file.state === "PROCESSING_FAILED"
                        ? t("failed")
                        : file.state}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {canContinue && (
          <div className="mt-8 flex justify-end">
            <Link href={`/matters/${matterId}/documents`}>
              <Button variant="primary">
                {t("continueToInbox")}
                <ChevronRight className="size-4" strokeWidth={1.5} />
              </Button>
            </Link>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function ProcessingUnavailable({ matterId }: { matterId: string }) {
  const t = useTranslations("processing");
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
