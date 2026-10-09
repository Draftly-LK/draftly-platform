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
import { editSnapshot } from "./document-edit-snapshot";

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
  const [reviewedInbox, setReviewedInbox] = useState<ApiDocumentInbox | null>(
    null,
  );
  const [refused, setRefused] = useState(false);
  const [retryKind, setRetryKind] = useState<"group" | "page" | null>(null);
  const pendingEdit = useRef<ManualIntent | undefined>(undefined);
  const latestInbox = useRef(inbox);
  latestInbox.current = inbox;
  const pageControl = useRef<HTMLInputElement>(null);
  const groupControls = useRef<HTMLDivElement>(null);
  const focusRenewed = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    if (focusRenewed.current) {
      focusRenewed.current = false;
      (sourceId
        ? pageControl.current
        : groupControls.current?.querySelector("select")
      )?.focus();
    }
  });
  useEffect(() => {
    const scopeGeneration = ++generation.current;
    setRanges([]);
    setSourceId("");
    setCreatedId(null);
    setError(null);
    setReviewedInbox(null);
    setRefused(false);
    pendingEdit.current = undefined;
    setRetryKind(null);
    return () => {
      generation.current = scopeGeneration + 1;
    };
  }, [inbox.matterId]);
  const source = reviewedInbox?.sourceFiles.find(
    (item) => item.id === sourceId,
  );
  const sourceIds = sourceId
    ? [sourceId]
    : ranges.map((range) => range.sourceFileId);
  const changed = (latest: ApiDocumentInbox) =>
    reviewedInbox !== null &&
    editSnapshot(reviewedInbox, sourceIds) !== editSnapshot(latest, sourceIds);
  const stale = refused || changed(inbox);
  function beginReview() {
    if (pendingEdit.current) clearManualIntent(pendingEdit.current);
    pendingEdit.current = undefined;
    setRetryKind(null);
    setReviewedInbox(inbox);
    setRefused(false);
    setRetire([]);
    setReason("");
    setDisposition("blank");
    setError(null);
  }
  function renew() {
    focusRenewed.current = true;
    beginReview();
    const accounting = inbox.pageAccounting?.find(
      (item) => item.sourceFileId === sourceIds[0],
    );
    if (sourceId) {
      if (
        !inbox.sourceFiles.some(
          (item) =>
            item.id === sourceId &&
            !["SUPERSEDED", "REJECTED"].includes(item.state),
        )
      )
        setSourceId("");
      const currentPage =
        pageNumber <= (accounting?.pageCount ?? 0)
          ? pageNumber
          : (accounting?.unclaimedPageNumbers[0] ?? 1);
      setPageNumber(currentPage);
      setDisposition(
        accounting?.blankPageNumbers.includes(currentPage)
          ? "blank"
          : accounting?.unsupportedPageNumbers.includes(currentPage)
            ? "unsupported"
            : "review_required",
      );
    } else {
      const start = accounting?.unclaimedPageNumbers[0];
      if (start === undefined) setRanges([]);
      else {
        let end = start;
        while (accounting?.unclaimedPageNumbers.includes(end + 1)) end++;
        setRanges([
          {
            sourceFileId: accounting!.sourceFileId,
            pageStart: start,
            pageEnd: end,
          },
        ]);
      }
    }
  }
  async function save(kind: "group" | "page", replay = false) {
    if (busy || ((stale || retryKind !== null) && !replay)) return;
    const current = generation.current;
    setBusy(true);
    setError(null);
    let intent: ManualIntent | undefined;
    let responseReceived = false;
    try {
      const actor = await getMe(getToken);
      if (current !== generation.current) return;
      if (!replay && changed(latestInbox.current)) return;
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
      pendingEdit.current = intent;
      if (!replay && changed(latestInbox.current)) {
        if (!intent.reused) clearManualIntent(intent);
        return;
      }
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
        responseReceived = true;
        clearManualIntent(intent);
        pendingEdit.current = undefined;
        setRetryKind(null);
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
        responseReceived = true;
        clearManualIntent(intent);
        pendingEdit.current = undefined;
        setRetryKind(null);
        if (current !== generation.current) return;
        setSourceId("");
        setReason("");
      }
      onChange();
    } catch (cause: unknown) {
      if (responseReceived && current === generation.current) {
        // The server already acknowledged the command; renew the read, never
        // create a second command merely because its follow-up GET failed.
        setRefused(true);
        setRetryKind(null);
        onChange();
      } else if (intent && cause instanceof ApiError && cause.status === 412) {
        clearManualIntent(intent);
        if (current === generation.current) {
          setRefused(true);
          pendingEdit.current = undefined;
          setRetryKind(null);
          onChange();
        }
      } else if (intent && current === generation.current) {
        setRetryKind(kind);
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
      {(stale || retryKind) && (
        <div role="status" className="space-y-2 text-sm">
          <p className="text-amber-text">{t("editsChanged")}</p>
          <Button disabled={busy} onClick={renew}>
            {t("renewEdits")}
          </Button>
          {retryKind && (
            <Button disabled={busy} onClick={() => void save(retryKind, true)}>
              {t("retryPending")}
            </Button>
          )}
        </div>
      )}
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
                    beginReview();
                    setSourceId("");
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
                    beginReview();
                    setRanges([]);
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
        <div ref={groupControls} className="space-y-3">
          <DocumentPageEditor
            sources={reviewedInbox?.sourceFiles ?? []}
            ranges={ranges}
            onChange={setRanges}
            disabled={busy || stale || retryKind !== null}
          />
          <Button
            disabled={
              busy ||
              stale ||
              retryKind !== null ||
              !validPageRanges(ranges, reviewedInbox?.sourceFiles ?? [])
            }
            onClick={() => void save("group")}
          >
            {t("createGroup")}
          </Button>
        </div>
      )}
      {source && (
        <fieldset
          disabled={busy || stale || retryKind !== null}
          className="space-y-3"
        >
          <legend className="text-sm font-medium">
            {t("disposition")} · {source.originalFilename}
          </legend>
          <label className="block text-sm">
            {t("pageNumber")}
            <input
              ref={pageControl}
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
            reviewedInbox?.documents
              .filter(
                (document) =>
                  document.fragments.length > 0 &&
                  document.versionRelationship !== "SUPERSEDED" &&
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
              stale ||
              retryKind !== null ||
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
