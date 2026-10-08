"use client";

import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock3,
  RefreshCw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button, buttonClass } from "@/components/ui/button";
import {
  ApiError,
  isApiEnabled,
  type TokenProvider,
  apiErrorMessage,
} from "@/lib/api/client";
import {
  getSourceFile,
  getSourceProcessingStatus,
  listSourceFiles,
  processSourceFile,
} from "@/lib/api/documents";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import type { ApiSourceProcessingStatus } from "@/types/rta";

interface ProcessingEntry extends ApiSourceProcessingStatus {
  isProcessing?: boolean;
  statusUnavailable?: boolean;
}

class ProcessingPaginationError extends Error {}

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
  const fileStateLabel = useEnumLabel("enums.sourceFileState");
  const [entries, setEntries] = useState<ProcessingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  const activeRequests = useRef(new Set<string>());

  useEffect(() => {
    const currentGeneration = ++generation.current;
    const isCurrent = () => generation.current === currentGeneration;
    setLoading(true);
    setLoaded(false);
    setEntries([]);
    setError(null);
    async function load() {
      const all: ProcessingEntry[] = [];
      const cursors = new Set<string>();
      const sourceIds = new Set<string>();
      let cursor: string | undefined;
      do {
        const response = await listSourceFiles(getToken, matterId, {
          limit: 50,
          cursor,
        });
        if (!isCurrent()) return;
        // Bound concurrent reads; failed status reads stay explicitly unknown.
        for (let index = 0; index < response.items.length; index += 5) {
          const batch = await Promise.all(
            response.items
              .slice(index, index + 5)
              .map(async (file): Promise<ProcessingEntry> => {
                try {
                  return await getSourceProcessingStatus(getToken, file.id);
                } catch {
                  return {
                    sourceFile: file,
                    latestRun: null,
                    statusUnavailable: true,
                  };
                }
              }),
          );
          if (!isCurrent()) return;
          for (const entry of batch) {
            if (!sourceIds.has(entry.sourceFile.id)) {
              sourceIds.add(entry.sourceFile.id);
              all.push(entry);
            }
          }
        }
        if (!response.page.hasMore) break;
        const next = response.page.nextCursor;
        if (!next || cursors.has(next) || cursors.size >= 100)
          throw new ProcessingPaginationError();
        cursors.add(next);
        cursor = next;
      } while (isCurrent());
      if (isCurrent()) {
        setEntries(all);
        setLoaded(true);
      }
    }
    void load()
      .catch((cause: unknown) => {
        if (isCurrent())
          setError(
            cause instanceof ProcessingPaginationError
              ? t("paginationError")
              : apiErrorMessage(cause, t("error")),
          );
      })
      .finally(() => {
        if (isCurrent()) setLoading(false);
      });
    return () => {
      generation.current += 1;
    };
  }, [getToken, matterId, refresh, t]);

  async function handleProcess(entry: ProcessingEntry) {
    const id = entry.sourceFile.id;
    if (activeRequests.current.has(id)) return;
    activeRequests.current.add(id);
    const currentGeneration = generation.current;
    const isCurrent = () => currentGeneration === generation.current;
    const replace = (next: ProcessingEntry) => {
      if (isCurrent())
        setEntries((current) =>
          current.map((item) => (item.sourceFile.id === id ? next : item)),
        );
    };
    replace({ ...entry, isProcessing: true });
    setError(null);
    try {
      // Refresh the concurrency token immediately before every initial attempt or retry.
      const file = await getSourceFile(getToken, id);
      if (!isCurrent()) return;
      if (file.state !== "STORED" && file.state !== "PROCESSING_FAILED") {
        const status = await getSourceProcessingStatus(getToken, id);
        if (!isCurrent()) return;
        replace(status);
        setError(t("staleSource"));
        return;
      }
      await processSourceFile(getToken, id, file.version);
      replace(await getSourceProcessingStatus(getToken, id));
    } catch (cause: unknown) {
      if (!isCurrent()) return;
      setError(
        cause instanceof ApiError && cause.status === 412
          ? t("staleSource")
          : apiErrorMessage(cause, t("error")),
      );
      try {
        replace(await getSourceProcessingStatus(getToken, id));
      } catch {
        replace({
          ...entry,
          latestRun: null,
          statusUnavailable: true,
          isProcessing: false,
        });
      }
    } finally {
      activeRequests.current.delete(id);
    }
  }

  const busy = entries.some((entry) => entry.isProcessing);
  const canContinue =
    loaded &&
    !loading &&
    !busy &&
    !error &&
    entries.length > 0 &&
    entries.every(
      ({ sourceFile, latestRun, statusUnavailable }) =>
        !statusUnavailable &&
        sourceFile.state === "PROCESSED" &&
        latestRun?.state === "succeeded" &&
        latestRun.outcome === "PROCESSED",
    );
  const inbox = `/matters/${matterId}/documents`;

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="mb-4 flex flex-wrap justify-end gap-2">
          <Button
            disabled={loading || busy}
            onClick={() => setRefresh((value) => value + 1)}
          >
            <RefreshCw
              aria-hidden="true"
              className="size-4"
              strokeWidth={1.5}
            />
            {t("refresh")}
          </Button>
        </div>
        {error && (
          <div
            role="alert"
            className="border-red bg-red-bg text-red mb-4 flex items-start gap-2 rounded border p-4"
          >
            <AlertCircle
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0"
              strokeWidth={1.5}
            />
            <p className="text-sm">{error}</p>
          </div>
        )}
        {loading && (
          <p role="status" className="text-muted-ink py-6">
            {t("loading")}
          </p>
        )}
        {!loading && loaded && entries.length === 0 && (
          <div className="border-border bg-surface rounded-card border p-6 text-center">
            <p className="text-muted-ink mb-4">{t("emptyState")}</p>
            <Link className={buttonClass("primary")} href={inbox}>
              {t("uploadDocuments")}
            </Link>
          </div>
        )}
        {!loading && entries.length > 0 && (
          <ul className="divide-border border-border divide-y border-y">
            {entries.map((entry) => {
              const file = entry.sourceFile;
              const run = entry.latestRun;
              const success =
                file.state === "PROCESSED" &&
                run?.state === "succeeded" &&
                run.outcome === "PROCESSED" &&
                !entry.statusUnavailable;
              const failed =
                file.state === "PROCESSING_FAILED" ||
                run?.state === "failed" ||
                file.state === "REJECTED";
              const waiting =
                file.state === "STORED" && !entry.statusUnavailable;
              const processing =
                entry.isProcessing || file.state === "PROCESSING";
              const manual = success && run.manualReviewRequired;
              const StatusIcon =
                success && !manual
                  ? CheckCircle2
                  : failed || manual || entry.statusUnavailable
                    ? AlertCircle
                    : Clock3;
              const label = processing
                ? t("processing")
                : file.state === "SUPERSEDED" || file.state === "REJECTED"
                  ? fileStateLabel(file.state)
                  : success
                    ? manual
                      ? t("manualReviewRequired")
                      : t("succeeded")
                    : failed
                      ? t("failed")
                      : waiting
                        ? fileStateLabel(file.state)
                        : t("unknownOutcome");
              const reason = run?.failureReason ?? file.failureReason;
              return (
                <li key={file.id} className="py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="break-words font-medium">
                        {file.originalFilename}
                      </p>
                      {file.pageCount !== null && (
                        <p className="text-muted-ink text-sm">
                          {t("pageCount", { count: file.pageCount })}
                        </p>
                      )}
                      <p className="mt-2 flex items-start gap-2 text-sm">
                        <StatusIcon
                          aria-hidden="true"
                          className="mt-0.5 size-4 shrink-0"
                          strokeWidth={1.5}
                        />
                        {label}
                      </p>
                      {failed && (
                        <p className="text-muted-ink mt-2 text-sm">
                          {reason
                            ? t(`failure.${reason}`)
                            : t("unknownFailure")}
                        </p>
                      )}
                      {run && (
                        <ul className="text-muted-ink mt-2 space-y-1 text-sm">
                          {run.pageOutcomes.flatMap((page) => [
                            page.qualityStatus !== "normal" ? (
                              <li key={`${page.pageNo}-quality`}>
                                {t(`pageQuality.${page.qualityStatus}`, {
                                  page: page.pageNo,
                                })}
                              </li>
                            ) : null,
                            page.rotationStatus === "rotation_uncertain" ? (
                              <li key={`${page.pageNo}-rotation`}>
                                {t("rotationUncertain", { page: page.pageNo })}
                              </li>
                            ) : null,
                          ])}
                        </ul>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {(waiting ||
                        file.state === "PROCESSING_FAILED" ||
                        entry.isProcessing) && (
                        <Button
                          disabled={processing || entry.statusUnavailable}
                          aria-busy={entry.isProcessing || undefined}
                          onClick={() => void handleProcess(entry)}
                        >
                          {processing
                            ? t("processing")
                            : file.state === "PROCESSING_FAILED"
                              ? t("retry")
                              : t("process")}
                        </Button>
                      )}
                      {(failed ||
                        manual ||
                        (!success && !waiting && !processing)) && (
                        <Link className={buttonClass("secondary")} href={inbox}>
                          {t("manualReview")}
                        </Link>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {canContinue && (
          <div className="mt-8 flex justify-end">
            <Link className={buttonClass("primary")} href={inbox}>
              {t("continueToInbox")}
              <ChevronRight
                aria-hidden="true"
                className="size-4"
                strokeWidth={1.5}
              />
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
        <div className="border-border bg-surface rounded-card border p-6">
          <AlertCircle
            aria-hidden="true"
            className="text-amber-text size-5"
            strokeWidth={1.5}
          />
          <p className="mt-2 text-sm">{t("backendNotConfigured")}</p>
        </div>
      </div>
    </AppShell>
  );
}
