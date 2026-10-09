"use client";

import {
  AlertTriangle,
  Check,
  CircleCheck,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  ApiError,
  apiErrorMessage,
  type TokenProvider,
} from "@/lib/api/client";
import {
  getDetectedDocument,
  getCompleteDocumentInbox,
  getDocumentInterpretations,
  type FragmentRangeInput,
  recordBoundaryDecision,
  recordClassificationDecision,
  refreshDocumentExtraction,
} from "@/lib/api/documents";
import { getRtaDocumentClasses, type ApiRtaDocumentClass } from "@/lib/api/rta";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import { getMe } from "@/lib/api/auth";
import {
  pendingOperationIntent,
  clearManualIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import { DocumentPageEditor, validPageRanges } from "./document-page-editor";
import { documentSnapshot, editSnapshot } from "./document-edit-snapshot";
import type {
  ApiDetectedDocument,
  ApiDocumentInbox,
  ApiInterpretationHistory,
} from "@/types/rta";

/** Confirmed by the lawyer: nothing left to decide about what the document is or which pages it spans. */
export function isDocumentDecided(document: ApiDetectedDocument): boolean {
  return (
    document.classStatus === "LAWYER_CONFIRMED" &&
    document.boundaryStatus === "CONFIRMED" &&
    document.extractionState === "current" &&
    document.versionRelationship !== "SUPERSEDED"
  );
}

/**
 * The two lawyer decisions every detected document needs: what it is, and
 * which pages it spans. Shared by the full review (page images and fields)
 * and the classification-only fallback, so both finish the same way.
 */
export function DocumentDecisions({
  getToken,
  matterId,
  documentId,
  onChange,
}: {
  getToken: TokenProvider;
  matterId: string;
  documentId: string;
  /** Called with the document after it loads and after every decision. */
  onChange?: (document: ApiDetectedDocument) => void;
}) {
  const t = useTranslations("classificationReview");
  const tRoot = useTranslations();
  const operations = useTranslations("documentOperations");
  const [inbox, setInbox] = useState<ApiDocumentInbox | null>(null);
  const [history, setHistory] = useState<ApiInterpretationHistory | null>(null);
  const [ranges, setRanges] = useState<FragmentRangeInput[]>([]);
  const [retire, setRetire] = useState<
    { documentId: string; version: number }[]
  >([]);
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const [readFailed, setReadFailed] = useState(false);
  const [reviewed, setReviewed] = useState<ApiDetectedDocument | null>(null);
  const [reviewedInbox, setReviewedInbox] = useState<ApiDocumentInbox | null>(
    null,
  );
  const [editStale, setEditStale] = useState(false);
  const classControl = useRef<HTMLSelectElement>(null);
  const focusRenewed = useRef(false);
  const pendingEdit = useRef<ManualIntent | undefined>(undefined);
  const [retryKind, setRetryKind] = useState<"class" | "boundary" | null>(null);
  const generation = useRef(0);
  const textFor = (key: string, fallbackId: string) =>
    tRoot.has(key)
      ? typeof tRoot.raw(key) === "string"
        ? tRoot(key)
        : tRoot.has(`${key}.label`)
          ? tRoot(`${key}.label`)
          : humanizeMessageKey(fallbackId.split(".").pop() ?? fallbackId)
      : humanizeMessageKey(fallbackId.split(".").pop() ?? fallbackId);
  const [document, setDocument] = useState<ApiDetectedDocument | null>(null);
  const [classes, setClasses] = useState<ApiRtaDocumentClass[]>([]);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState<"class" | "boundary" | "refresh" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (focusRenewed.current && saving === null && !editStale) {
      focusRenewed.current = false;
      classControl.current?.focus();
    }
  }, [saving, editStale]);

  useEffect(() => {
    let active = true;
    const scopeGeneration = ++generation.current;
    setDocument(null);
    setInbox(null);
    setHistory(null);
    setReadFailed(false);
    setEditStale(false);
    setReviewed(null);
    setReviewedInbox(null);
    pendingEdit.current = undefined;
    setRetryKind(null);
    setRetire([]);
    Promise.all([
      getDetectedDocument(getToken, documentId),
      getRtaDocumentClasses(getToken),
      getCompleteDocumentInbox(getToken, matterId),
      getDocumentInterpretations(getToken, documentId),
    ])
      .then(([found, contract, queue, versions]) => {
        if (!active) return;
        if (found.id !== documentId || found.matterId !== matterId) {
          setError(t("documentNotFound"));
          return;
        }
        setDocument(found);
        setReviewed(found);
        setReviewedInbox(queue);
        setInbox(queue);
        setHistory(versions);
        setRanges(
          found.fragments.map(({ sourceFileId, pageStart, pageEnd }) => ({
            sourceFileId,
            pageStart,
            pageEnd,
          })),
        );
        setClasses(contract.classes);
        setSelected(found.classId ?? "");
        onChange?.(found);
      })
      .catch((cause: unknown) => {
        if (active) setError(apiErrorMessage(cause, t("error")));
      });
    return () => {
      active = false;
      generation.current = scopeGeneration + 1;
    };
    // `onChange` is a notification, not an input: re-running on a new callback would refetch for nothing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, getToken, matterId, t]);

  async function decide(
    kind: "class" | "boundary" | "refresh",
    replay = false,
  ) {
    if (
      !document ||
      !reviewed ||
      (kind !== "refresh" && (editStale || retryKind !== null) && !replay)
    )
      return;
    setSaving(kind);
    setError(null);
    const readGeneration = generation.current;
    const isCurrent = () => generation.current === readGeneration;
    let intent: ManualIntent | undefined;
    let submitted = false;
    let responseReceived = false;
    try {
      const actor = await getMe(getToken);
      if (!isCurrent()) return;
      const body =
        kind === "class"
          ? { classId: selected }
          : kind === "boundary"
            ? {
                fragments: ranges.map((range, orderInDocument) => ({
                  ...range,
                  orderInDocument,
                })),
                retireDocuments: retire,
              }
            : {};
      intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `document:${documentId}:${kind}`,
        body,
        kind === "refresh" ? document.version : reviewed.version,
      );
      if (!isCurrent()) return;
      if (kind !== "refresh") {
        pendingEdit.current = intent;
        // A pending network replay retains its original key and precondition.
        // A new edited command must still describe the snapshot reviewed here.
        if (!intent.reused) {
          const [fresh, queue] = await Promise.all([
            getDetectedDocument(getToken, documentId),
            getCompleteDocumentInbox(getToken, matterId),
          ]);
          if (!isCurrent()) return;
          if (fresh.id !== documentId || fresh.matterId !== matterId)
            throw new Error(operations("readUnavailable"));
          const sources = [
            ...reviewed.fragments,
            ...ranges,
            ...(reviewedInbox?.documents
              .filter((item) =>
                retire.some((target) => target.documentId === item.id),
              )
              .flatMap((item) => item.fragments) ?? []),
          ].map((range) => range.sourceFileId);
          if (
            documentSnapshot(fresh) !== documentSnapshot(reviewed) ||
            editSnapshot(queue, sources) !==
              editSnapshot(reviewedInbox, sources)
          ) {
            clearManualIntent(intent);
            pendingEdit.current = undefined;
            setDocument(fresh);
            setInbox(queue);
            setEditStale(true);
            onChange?.(fresh);
            return;
          }
        }
      }
      setStorageUnavailable(!intent.persistent);
      const version = intent.expectedVersion ?? document.version;
      submitted = true;
      if (kind === "refresh")
        await refreshDocumentExtraction(
          getToken,
          documentId,
          version,
          intent.key,
        );
      else if (kind === "class")
        await recordClassificationDecision(
          getToken,
          documentId,
          { classId: selected },
          version,
          intent.key,
        );
      else
        await recordBoundaryDecision(
          getToken,
          documentId,
          {
            fragments: ranges.map((range, orderInDocument) => ({
              ...range,
              orderInDocument,
            })),
            retireDocuments: retire,
          },
          version,
          intent.key,
        );
      responseReceived = true;
      clearManualIntent(intent);
      pendingEdit.current = undefined;
      setRetryKind(null);
      // A replay returns its historical outcome. Only a new read can establish current authority.
      const updated = await getDetectedDocument(getToken, documentId);
      if (!isCurrent()) return;
      if (updated.id !== documentId || updated.matterId !== matterId)
        throw new Error(operations("readUnavailable"));
      setDocument(updated);
      setReviewed(updated);
      setEditStale(false);
      setSelected(updated.classId ?? "");
      setReadFailed(false);
      setRanges(
        updated.fragments.map(({ sourceFileId, pageStart, pageEnd }) => ({
          sourceFileId,
          pageStart,
          pageEnd,
        })),
      );
      setRetire([]);
      onChange?.(updated);
      const [queue, versions] = await Promise.all([
        getCompleteDocumentInbox(getToken, matterId),
        getDocumentInterpretations(getToken, documentId),
      ]);
      if (isCurrent()) {
        setInbox(queue);
        setReviewedInbox(queue);
        setHistory(versions);
      }
    } catch (cause: unknown) {
      if (isCurrent()) {
        setError(apiErrorMessage(cause, t("error")));
        // The mutation may have committed. Withhold completion until the current read succeeds.
        setReadFailed(true);
        onChange?.({ ...document, extractionState: "unavailable" });
        if (intent && !submitted && !intent.reused) {
          clearManualIntent(intent);
          pendingEdit.current = undefined;
          setRetryKind(null);
          if (kind !== "refresh") setEditStale(true);
        } else if (
          intent &&
          cause instanceof ApiError &&
          cause.status === 412
        ) {
          clearManualIntent(intent);
          pendingEdit.current = undefined;
          setRetryKind(null);
          if (kind !== "refresh") setEditStale(true);
        } else if (intent && kind !== "refresh" && !responseReceived) {
          setRetryKind(kind);
        }
        try {
          const fresh = await getDetectedDocument(getToken, documentId);
          if (
            isCurrent() &&
            fresh.id === documentId &&
            fresh.matterId === matterId
          ) {
            setDocument(fresh);
            if (documentSnapshot(fresh) !== documentSnapshot(reviewed))
              setEditStale(true);
            setReadFailed(false);
            onChange?.(fresh);
          }
        } catch {
          /* A failed current read keeps all completion and mutation controls closed. */
        }
      }
    } finally {
      if (isCurrent()) setSaving(null);
    }
  }

  async function renewEdits() {
    setSaving("boundary");
    const epoch = generation.current;
    try {
      const [fresh, queue] = await Promise.all([
        getDetectedDocument(getToken, documentId),
        getCompleteDocumentInbox(getToken, matterId),
      ]);
      if (epoch !== generation.current) return;
      if (fresh.id !== documentId || fresh.matterId !== matterId)
        throw new Error(operations("readUnavailable"));
      if (pendingEdit.current) clearManualIntent(pendingEdit.current);
      pendingEdit.current = undefined;
      setRetryKind(null);
      setDocument(fresh);
      setReviewed(fresh);
      setInbox(queue);
      setReviewedInbox(queue);
      setSelected(fresh.classId ?? "");
      setRanges(
        fresh.fragments.map(({ sourceFileId, pageStart, pageEnd }) => ({
          sourceFileId,
          pageStart,
          pageEnd,
        })),
      );
      setRetire([]);
      setEditStale(false);
      setError(null);
      setReadFailed(false);
      focusRenewed.current = true;
      onChange?.(fresh);
    } catch (cause) {
      if (epoch === generation.current)
        setError(apiErrorMessage(cause, t("error")));
    } finally {
      if (epoch === generation.current) {
        setSaving(null);
      }
    }
  }

  if (!document) {
    return (
      <section className="border-border bg-surface rounded-card border p-4">
        {error ? (
          <p role="alert" className="text-red text-sm">
            {error}
          </p>
        ) : (
          <LoaderCircle
            aria-label={t("loading")}
            className="size-5 animate-spin"
            strokeWidth={1.5}
          />
        )}
      </section>
    );
  }

  const classConfirmed =
    document.classStatus === "LAWYER_CONFIRMED" &&
    selected === document.classId;
  const boundaryConfirmed = document.boundaryStatus === "CONFIRMED";
  const pages = document.fragments
    .map((fragment) =>
      t("pageRange", { start: fragment.pageStart, end: fragment.pageEnd }),
    )
    .join(", ");

  return (
    <section className="border-border bg-surface rounded-card space-y-4 border p-4">
      {storageUnavailable && (
        <p role="status" className="text-amber-text text-sm">
          {operations("storageUnavailable")}
        </p>
      )}
      {readFailed && (
        <div role="status" className="space-y-2 text-sm">
          <p className="text-amber-text">{operations("readUnavailable")}</p>
          <Button onClick={() => window.location.reload()}>
            {operations("reloadCurrent")}
          </Button>
        </div>
      )}
      <h2 className="font-semibold">{t("decisionsTitle")}</h2>
      {(editStale || retryKind) && (
        <div role="status" className="space-y-2 text-sm">
          <p className="text-amber-text">{operations("editsChanged")}</p>
          <Button disabled={saving !== null} onClick={() => void renewEdits()}>
            {operations("renewEdits")}
          </Button>
          {retryKind && (
            <Button
              disabled={saving !== null || readFailed}
              onClick={() => void decide(retryKind, true)}
            >
              {operations("retryPending")}
            </Button>
          )}
        </div>
      )}
      {error ? (
        <p role="alert" className="text-red text-sm">
          {error}
        </p>
      ) : null}
      <div
        role="status"
        className="border-border rounded-control border p-3 text-sm"
      >
        <p className="flex items-start gap-2">
          {document.extractionState === "current" ? (
            <CircleCheck className="size-4 shrink-0" aria-hidden="true" />
          ) : (
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          )}
          {t(`extraction.${document.extractionState ?? "unavailable"}`)}
        </p>
        {document.extractionState !== "current" &&
          classConfirmed &&
          boundaryConfirmed &&
          document.versionRelationship !== "SUPERSEDED" && (
            <Button
              size="sm"
              className="mt-3"
              disabled={saving !== null || readFailed}
              onClick={() => void decide("refresh")}
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              {t("refreshExtraction")}
            </Button>
          )}
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium">
          {t("selectClass")}
          <select
            ref={classControl}
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            disabled={
              saving !== null || readFailed || editStale || retryKind !== null
            }
            className="border-border-control bg-surface rounded-control mt-1 min-h-10 w-full border px-3 py-2"
          >
            <option value="">{t("chooseClass")}</option>
            {classes.map((item) => (
              <option key={item.id} value={item.id}>
                {textFor(item.labelKey, item.id)}
              </option>
            ))}
          </select>
        </label>
        {classConfirmed ? (
          <p className="text-teal flex items-center gap-1.5 text-sm">
            <CircleCheck
              aria-hidden="true"
              className="size-4"
              strokeWidth={1.5}
            />
            {t("classConfirmed")}
          </p>
        ) : (
          <Button
            size="sm"
            disabled={
              !selected ||
              saving !== null ||
              readFailed ||
              editStale ||
              retryKind !== null ||
              document.versionRelationship === "SUPERSEDED"
            }
            onClick={() => void decide("class")}
          >
            {saving === "class" ? (
              <LoaderCircle
                aria-hidden="true"
                className="size-4 animate-spin"
                strokeWidth={1.5}
              />
            ) : (
              <Check aria-hidden="true" className="size-4" strokeWidth={1.5} />
            )}
            {t("confirmClassification")}
          </Button>
        )}
      </div>

      <div className="border-border space-y-2 border-t pt-4">
        <p className="text-sm font-medium">{t("pagesLabel")}</p>
        <p className="text-muted-ink text-sm">{pages}</p>
        <DocumentPageEditor
          sources={reviewedInbox?.sourceFiles ?? []}
          ranges={ranges}
          onChange={setRanges}
          disabled={
            saving !== null ||
            readFailed ||
            editStale ||
            retryKind !== null ||
            document.versionRelationship === "SUPERSEDED"
          }
        />
        {(inbox?.documents ?? []).filter(
          (item) =>
            item.id !== documentId && item.versionRelationship !== "SUPERSEDED",
        ).length > 0 && (
          <fieldset
            className="space-y-2"
            disabled={
              saving !== null ||
              readFailed ||
              editStale ||
              retryKind !== null ||
              document.versionRelationship === "SUPERSEDED"
            }
          >
            <legend className="text-sm font-medium">
              {operations("mergeDocuments")}
            </legend>
            <p className="text-muted-ink text-sm">{operations("mergeHint")}</p>
            {inbox?.documents
              .filter(
                (item) =>
                  item.id !== documentId &&
                  item.versionRelationship !== "SUPERSEDED",
              )
              .map((item) => (
                <label key={item.id} className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={retire.some(
                      (entry) => entry.documentId === item.id,
                    )}
                    onChange={(e) =>
                      setRetire((current) =>
                        e.target.checked
                          ? [
                              ...current,
                              { documentId: item.id, version: item.version },
                            ]
                          : current.filter(
                              (entry) => entry.documentId !== item.id,
                            ),
                      )
                    }
                  />
                  {textFor(
                    `rta.doc.${item.classId?.split(".").pop()}`,
                    item.classId ?? "unknown",
                  )}{" "}
                  ·{" "}
                  {item.fragments
                    .map(
                      (range) =>
                        `${inbox.sourceFiles.find((source) => source.id === range.sourceFileId)?.originalFilename ?? range.sourceFileId}: ${t("pageRange", { start: range.pageStart, end: range.pageEnd })}`,
                    )
                    .join(", ")}
                </label>
              ))}
          </fieldset>
        )}
        <Button
          size="sm"
          disabled={
            saving !== null ||
            readFailed ||
            editStale ||
            retryKind !== null ||
            document.versionRelationship === "SUPERSEDED" ||
            !validPageRanges(ranges, inbox?.sourceFiles ?? [])
          }
          onClick={() => void decide("boundary")}
        >
          <Check aria-hidden="true" className="size-4" />
          {operations("saveGrouping")}
        </Button>
      </div>
      {history && (
        <details className="border-border border-t pt-3">
          <summary className="cursor-pointer text-sm font-medium">
            {operations("history")}
          </summary>
          <ol className="mt-3 space-y-3 text-sm">
            {history.snapshots.map((snapshot) => (
              <li key={snapshot.generation}>
                <p className="font-medium">
                  {operations("generation", {
                    generation: snapshot.generation,
                  })}{" "}
                  ·{" "}
                  {textFor(
                    snapshot.classId ?? "unknown",
                    snapshot.classId ?? "unknown",
                  )}
                </p>
                {snapshot.fragments.map((range, index) => (
                  <p key={index} className="break-words">
                    {inbox?.sourceFiles.find(
                      (source) => source.id === range.sourceFileId,
                    )?.originalFilename ?? range.sourceFileId}
                    :{" "}
                    {t("pageRange", {
                      start: range.pageStart,
                      end: range.pageEnd,
                    })}
                  </p>
                ))}
                {history.refreshRuns
                  .filter((run) => run.generation === snapshot.generation)
                  .map((run) => (
                    <p key={run.id} className="text-muted-ink">
                      {operations(
                        run.outcome === "PROCESSED"
                          ? "refreshSucceeded"
                          : "refreshFailed",
                      )}{" "}
                      · {new Date(run.startedAt).toLocaleString()}
                    </p>
                  ))}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
