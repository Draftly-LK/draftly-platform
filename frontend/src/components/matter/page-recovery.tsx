"use client";

import { AlertTriangle, CircleCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button, buttonClass } from "@/components/ui/button";
import { getMe } from "@/lib/api/auth";
import {
  ApiError,
  apiErrorMessage,
  type TokenProvider,
} from "@/lib/api/client";
import {
  createDocumentGroup,
  getDetectedDocument,
  recordPageDisposition,
  type FragmentRangeInput,
} from "@/lib/api/documents";
import {
  clearManualIntent,
  pendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import type { ApiDocumentInbox } from "@/types/rta";
import { DocumentPageEditor, validPageRanges } from "./document-page-editor";

export function PageRecovery({
  getToken,
  inbox,
  onChange,
}: {
  getToken: TokenProvider;
  inbox: ApiDocumentInbox;
  onChange: () => void;
}) {
  const t = useTranslations("documentOperations");
  const [ranges, setRanges] = useState<FragmentRangeInput[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [pageNumber, setPageNumber] = useState(1);
  const [disposition, setDisposition] = useState<
    "blank" | "unsupported" | "review_required"
  >("blank");
  const [retire, setRetire] = useState<
    { documentId: string; version: number }[]
  >([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    const scopeGeneration = ++generation.current;
    setRanges([]);
    setSourceId("");
    setCreatedId(null);
    setError(null);
    return () => {
      generation.current = scopeGeneration + 1;
    };
  }, [inbox.matterId]);
  const source = inbox.sourceFiles.find((item) => item.id === sourceId);
  async function save(kind: "group" | "page") {
    if (busy) return;
    const current = generation.current;
    setBusy(true);
    setError(null);
    let intent: ManualIntent | undefined;
    try {
      const actor = await getMe(getToken);
      if (current !== generation.current) return;
      const body =
        kind === "group"
          ? {
              fragments: ranges.map((range, orderInDocument) => ({
                ...range,
                orderInDocument,
              })),
            }
          : {
              pageNumber,
              disposition,
              reason: reason.trim(),
              ...(retire.length ? { retireDocuments: retire } : {}),
            };
      intent = await pendingOperationIntent(
        actor.id,
        inbox.matterId,
        kind === "group" ? "create-group" : `source:${sourceId}:page`,
        body,
        kind === "page" ? source?.version : undefined,
      );
      if (current !== generation.current) return;
      setStorageUnavailable(!intent.persistent);
      if (kind === "group") {
        const created = await createDocumentGroup(
          getToken,
          inbox.matterId,
          {
            fragments: ranges.map((range, orderInDocument) => ({
              ...range,
              orderInDocument,
            })),
          },
          intent.key,
        );
        clearManualIntent(intent);
        const fresh = await getDetectedDocument(getToken, created.id);
        if (current !== generation.current) return;
        if (fresh.matterId !== inbox.matterId) throw new Error(t("error"));
        setCreatedId(fresh.id);
        setRanges([]);
      } else if (source) {
        await recordPageDisposition(
          getToken,
          source.id,
          {
            pageNumber,
            disposition,
            reason: reason.trim(),
            ...(retire.length ? { retireDocuments: retire } : {}),
          },
          intent.expectedVersion ?? source.version,
          intent.key,
        );
        clearManualIntent(intent);
        if (current !== generation.current) return;
        setSourceId("");
        setReason("");
      }
      onChange();
    } catch (cause: unknown) {
      if (intent && cause instanceof ApiError && cause.status === 412) {
        clearManualIntent(intent);
        if (current === generation.current) onChange();
      }
      if (current === generation.current)
        setError(apiErrorMessage(cause, t("error")));
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }
  if (!inbox.pageAccounting?.length) return null;
  return (
    <section className="border-border bg-surface rounded-card mb-6 space-y-4 border p-4">
      <h2 className="font-semibold">{t("accountingTitle")}</h2>
      {error && (
        <p role="alert" className="text-red text-sm">
          {error}
        </p>
      )}
      {storageUnavailable && (
        <p role="status" className="text-amber-text text-sm">
          {t("storageUnavailable")}
        </p>
      )}
      <ul className="divide-border divide-y">
        {inbox.pageAccounting.map((accounting) => (
          <li key={accounting.sourceFileId} className="space-y-2 py-3 text-sm">
            <p className="flex items-start gap-2 font-medium">
              {accounting.manualReviewRequired ? (
                <AlertTriangle aria-hidden="true" className="size-4 shrink-0" />
              ) : (
                <CircleCheck aria-hidden="true" className="size-4 shrink-0" />
              )}
              {
                inbox.sourceFiles.find(
                  (item) => item.id === accounting.sourceFileId,
                )?.originalFilename
              }
            </p>
            {accounting.pageCount === null && <p>{t("unknownPages")}</p>}
            {accounting.unclaimedPageNumbers.length > 0 && (
              <p>
                {t("unclaimed", {
                  pages: accounting.unclaimedPageNumbers.join(", "),
                })}
              </p>
            )}
            {accounting.overlappingPageNumbers.length > 0 && (
              <p>
                {t("overlap", {
                  pages: accounting.overlappingPageNumbers.join(", "),
                })}
              </p>
            )}
            {(accounting.outOfBoundsPageNumbers?.length ?? 0) > 0 && (
              <p>
                {t("outOfBounds", {
                  pages: accounting.outOfBoundsPageNumbers!.join(", "),
                })}
              </p>
            )}
            {accounting.blankPageNumbers.length > 0 && (
              <p>
                {t("blankPages", {
                  pages: accounting.blankPageNumbers.join(", "),
                })}
              </p>
            )}
            {accounting.unsupportedPageNumbers.length > 0 && (
              <p>
                {t("unsupportedPages", {
                  pages: accounting.unsupportedPageNumbers.join(", "),
                })}
              </p>
            )}
            {!accounting.manualReviewRequired && <p>{t("accounted")}</p>}
            <div className="flex flex-wrap gap-2">
              {accounting.unclaimedPageNumbers.length > 0 && (
                <Button
                  size="sm"
                  className="max-w-full whitespace-normal text-center"
                  disabled={busy}
                  onClick={() => {
                    const start = accounting.unclaimedPageNumbers[0];
                    if (start === undefined) return;
                    let end = start;
                    while (accounting.unclaimedPageNumbers.includes(end + 1))
                      end++;
                    setRanges([
                      {
                        sourceFileId: accounting.sourceFileId,
                        pageStart: start,
                        pageEnd: end,
                      },
                    ]);
                  }}
                >
                  {t("recover")}
                </Button>
              )}
              {accounting.pageCount !== null && (
                <Button
                  size="sm"
                  className="max-w-full whitespace-normal text-center"
                  disabled={busy}
                  onClick={() => {
                    setRetire([]);
                    setSourceId(accounting.sourceFileId);
                    setPageNumber(accounting.unclaimedPageNumbers[0] ?? 1);
                  }}
                >
                  {t("disposition")}
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {ranges.length > 0 && (
        <div className="space-y-3">
          <DocumentPageEditor
            sources={inbox.sourceFiles}
            ranges={ranges}
            onChange={setRanges}
            disabled={busy}
          />
          <Button
            disabled={busy || !validPageRanges(ranges, inbox.sourceFiles)}
            onClick={() => void save("group")}
          >
            {t("createGroup")}
          </Button>
        </div>
      )}
      {source && (
        <fieldset disabled={busy} className="space-y-3">
          <legend className="text-sm font-medium">
            {t("disposition")} · {source.originalFilename}
          </legend>
          <label className="block text-sm">
            {t("pageNumber")}
            <input
              className="border-border-control bg-surface rounded-control ml-3 min-h-10 w-24 border px-3"
              type="number"
              min={1}
              max={source.pageCount ?? undefined}
              value={pageNumber || ""}
              onChange={(e) => {
                setPageNumber(Number(e.target.value));
                setRetire([]);
              }}
            />
          </label>
          <label className="block text-sm">
            {t("disposition")}
            <select
              value={disposition}
              onChange={(e) => {
                setDisposition(e.target.value as typeof disposition);
                setRetire([]);
              }}
              className="border-border-control bg-surface rounded-control mt-1 min-h-10 w-full border px-3"
            >
              {(["blank", "unsupported", "review_required"] as const).map(
                (kind) => (
                  <option key={kind} value={kind}>
                    {t(kind)}
                  </option>
                ),
              )}
            </select>
          </label>
          {disposition !== "review_required" &&
            inbox.documents
              .filter(
                (document) =>
                  document.fragments.length > 0 &&
                  document.fragments.every(
                    (fragment) =>
                      fragment.sourceFileId === sourceId &&
                      fragment.pageStart === pageNumber &&
                      fragment.pageEnd === pageNumber,
                  ),
              )
              .map((document) => (
                <label
                  key={document.id}
                  className="flex items-start gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={retire.some(
                      (item) => item.documentId === document.id,
                    )}
                    onChange={(event) =>
                      setRetire((current) =>
                        event.target.checked
                          ? [
                              ...current,
                              {
                                documentId: document.id,
                                version: document.version,
                              },
                            ]
                          : current.filter(
                              (item) => item.documentId !== document.id,
                            ),
                      )
                    }
                  />
                  {t("retireSinglePage")}
                </label>
              ))}
          <label className="block text-sm">
            {t("reason")}
            <input
              value={reason}
              maxLength={2000}
              onChange={(e) => setReason(e.target.value)}
              className="border-border-control bg-surface rounded-control mt-1 min-h-10 w-full border px-3"
            />
          </label>
          <Button
            disabled={
              busy ||
              !reason.trim() ||
              !Number.isSafeInteger(pageNumber) ||
              pageNumber < 1 ||
              pageNumber > (source.pageCount ?? 0)
            }
            onClick={() => void save("page")}
          >
            {t("saveDisposition")}
          </Button>
        </fieldset>
      )}
      {createdId && (
        <Link
          href={`/matters/${inbox.matterId}/documents/${createdId}/review`}
          className={buttonClass("secondary")}
        >
          {t("reviewGroup")}
        </Link>
      )}
    </section>
  );
}
