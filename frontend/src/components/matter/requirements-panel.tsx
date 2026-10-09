"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Button, buttonClass } from "@/components/ui/button";
import {
  ApiError,
  apiErrorMessage,
  type TokenProvider,
} from "@/lib/api/client";
import { getMe } from "@/lib/api/auth";
import { getChecklist } from "@/lib/api/matters";
import { getCompleteDocumentInbox } from "@/lib/api/documents";
import {
  listRequirementLinks,
  requirementCommand,
  type RequirementOperation,
} from "@/lib/api/requirements";
import {
  pendingOperationIntent,
  clearManualIntent,
  clearPendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import { notifyMatterWorkChanged } from "@/lib/matter-work-events";
import type {
  ApiChecklist,
  ApiChecklistItemState,
  ApiDetectedDocument,
  ApiRequirementLink,
} from "@/types/rta";

const control =
  "border-border-control bg-surface rounded-control min-h-10 w-full border px-3 py-2 text-sm";
export function RequirementsPanel({
  matterId,
  getToken,
  mode,
  targetRequirementId,
}: {
  matterId: string;
  getToken: TokenProvider;
  mode: "documents" | "checks";
  targetRequirementId?: string;
}) {
  const t = useTranslations("requirementsWork");
  const root = useTranslations();
  const label = useEnumLabel("enums.requirementStatus");
  const id = useId();
  const [checklist, setChecklist] = useState<ApiChecklist | null>(null);
  const [documents, setDocuments] = useState<ApiDetectedDocument[]>([]);
  const [selected, setSelected] = useState<ApiChecklistItemState | null>(null);
  const [document, setDocument] = useState<ApiDetectedDocument | null>(null);
  const [links, setLinks] = useState<ApiRequirementLink[]>([]);
  const [method, setMethod] = useState("");
  const [dimension, setDimension] = useState("digitalReview");
  const [decision, setDecision] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [stale, setStale] = useState(false);
  const [inboxError, setInboxError] = useState(false);
  const [assessmentPending, setAssessmentPending] = useState(false);
  const epoch = useRef(0);
  const contextEpoch = useRef(0);
  const openedTarget = useRef<string | null>(null);
  const selectedHeading = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => {
    if (loading || !checklist || !targetRequirementId) return;
    const key = `${matterId}:${targetRequirementId}`;
    if (openedTarget.current === key) return;
    const item = checklist.items.find((row) => row.id === targetRequirementId);
    if (!item) return;
    openedTarget.current = key;
    setSelected(item);
  }, [checklist, loading, matterId, targetRequirementId]);
  useEffect(() => {
    if (selected?.id === targetRequirementId) selectedHeading.current?.focus();
  }, [selected, targetRequirementId]);
  useEffect(() => {
    const generation = contextEpoch;
    setBusy(false);
    return () => {
      generation.current++;
    };
  }, [matterId, getToken]);
  const pending = useRef<ManualIntent | null>(null);
  const title = (item: ApiChecklistItemState) =>
    root.has(item.labelKey)
      ? root(item.labelKey)
      : humanizeMessageKey(item.labelKey);
  const load = useCallback(async () => {
    const run = ++epoch.current;
    const [next, inbox] = await Promise.allSettled([
      getChecklist(getToken, matterId),
      getCompleteDocumentInbox(getToken, matterId),
    ]);
    if (run !== epoch.current) return null;
    if (inbox.status === "fulfilled") setDocuments(inbox.value.documents);
    else setDocuments([]);
    setInboxError(inbox.status === "rejected");
    if (next.status === "rejected") {
      setChecklist(null);
      throw next.reason;
    }
    setChecklist(next.value);
    return next.value;
  }, [getToken, matterId]);
  useEffect(() => {
    const generation = epoch;
    let alive = true;
    setLoading(true);
    setSelected(null);
    setError(null);
    setAssessmentPending(false);
    load()
      .catch((cause: unknown) => {
        if (!alive) return;
        if (
          cause instanceof ApiError &&
          cause.status === 404 &&
          cause.code === "checklist_snapshot_not_found"
        )
          setAssessmentPending(true);
        else setError(apiErrorMessage(cause, t("unavailable")));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
      generation.current++;
    };
  }, [load, t]);
  useEffect(() => {
    let alive = true;
    setLinks([]);
    if (selected)
      listRequirementLinks(getToken, matterId, selected.id)
        .then((value) => {
          if (alive) setLinks(value);
        })
        .catch(() => {
          if (alive) setError(t("unavailable"));
        });
    return () => {
      alive = false;
    };
  }, [getToken, matterId, selected, t]);
  const choose = (item: ApiChecklistItemState) => {
    if (busy || loading) return;
    setSelected(item);
    setDocument(null);
    setMethod("");
    setDecision("");
    setReason("");
    setStale(false);
    setError(null);
  };
  const renew = async () => {
    if (busy) return;
    const context = contextEpoch.current;
    if (pending.current) clearManualIntent(pending.current);
    pending.current = null;
    setBusy(true);
    try {
      if (selected) {
        const actor = await getMe(getToken);
        if (context !== contextEpoch.current) return;
        for (const operation of ["links", "decisions", "original-inspection"])
          clearPendingOperationIntent(
            actor.id,
            matterId,
            `requirement:${selected.id}:${operation}`,
          );
      }
      const fresh = await load();
      if (context !== contextEpoch.current) return;
      const item = fresh?.items.find((row) => row.id === selected?.id);
      if (item) {
        setSelected(item);
        setDocument(null);
        setStale(false);
      } else setSelected(null);
    } catch (cause) {
      if (context !== contextEpoch.current) return;
      setError(apiErrorMessage(cause, t("unavailable")));
    } finally {
      if (context === contextEpoch.current) setBusy(false);
    }
  };
  const save = async (
    operation: RequirementOperation,
    body: Record<string, unknown>,
  ) => {
    if (!selected || stale || busy) return;
    const context = contextEpoch.current;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      const actor = await getMe(getToken);
      if (context !== contextEpoch.current) return;
      const intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `requirement:${selected.id}:${operation}`,
        body,
        selected.version,
      );
      pending.current = intent;
      if (context !== contextEpoch.current) return;
      if (!intent.persistent) setNotice(t("retryStorage"));
      await requirementCommand(
        getToken,
        matterId,
        selected.id,
        operation,
        body,
        intent.expectedVersion ?? selected.version,
        intent.key,
      );
      clearManualIntent(intent);
      pending.current = null;
      if (context !== contextEpoch.current) return;
      notifyMatterWorkChanged(matterId);
      setSelected(null);
      setDocument(null);
      setNotice(t("saved"));
      await load();
    } catch (cause) {
      if (context !== contextEpoch.current) return;
      const changed =
        cause instanceof ApiError && [409, 412].includes(cause.status);
      setStale(changed);
      setError(
        changed ? t("changed") : apiErrorMessage(cause, t("saveFailed")),
      );
    } finally {
      if (context === contextEpoch.current) setBusy(false);
    }
  };
  const rows = (checklist?.items ?? [])
    .filter(
      (item) =>
        item.lifecycle !== "NOT_TRIGGERED" &&
        (mode === "checks" || item.computedResolution !== "SATISFIED"),
    )
    .sort(
      (a, b) =>
        Number(a.computedResolution === "SATISFIED") -
        Number(b.computedResolution === "SATISFIED"),
    );
  const groups = [...new Set(rows.map((row) => row.group))];
  const choices: Record<string, string[]> = {
    digitalReview: ["LAWYER_CONFIRMED", "REJECTED"],
    consistency: ["MATCHED", "MISMATCH"],
    currency: ["CURRENT", "STALE", "EXPIRED"],
    collection: ["REQUESTED", "RECEIVED", "MISSING"],
    applicability: selected?.waivable
      ? ["NOT_APPLICABLE", "WAIVED_BY_LAWYER"]
      : [],
  };
  return (
    <section
      aria-labelledby={`${id}-heading`}
      className="border-border rounded-card space-y-4 border p-4 sm:p-5"
    >
      <h2 id={`${id}-heading`} className="text-lg font-semibold">
        {t(mode === "documents" ? "documentsTitle" : "checksTitle")}
      </h2>

      {loading && <p role="status">{t("loading")}</p>}
      {error && (
        <p className="text-red text-sm" role="alert">
          {error}
        </p>
      )}
      {assessmentPending && (
        <div className="space-y-3">
          <p role="status" className="text-muted-ink text-sm">
            {t("assessmentPending")}
          </p>
          <Link
            className={buttonClass("primary")}
            href={`/matters/${encodeURIComponent(matterId)}/facts#transaction-scope`}
          >
            {t("reviewSetup")}
          </Link>
        </div>
      )}
      {notice && (
        <p className="text-muted-ink text-sm" role="status">
          {notice}
        </p>
      )}
      {!loading && checklist && rows.length === 0 && <p>{t("empty")}</p>}
      {inboxError && (
        <p role="alert" className="text-amber-text text-sm">
          {t("inboxUnavailable")}
        </p>
      )}
      <Link
        className="text-link text-sm underline"
        href={`/matters/${matterId}/documents`}
      >
        {t("collectDocuments")}
      </Link>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-4">
          {groups.map((group) => (
            <section key={group}>
              <h3 className="text-muted-ink mb-2 text-sm font-semibold">
                {t.has(`groups.${group}`)
                  ? t(`groups.${group}`)
                  : t("groups.OFFICE_ADDED")}
              </h3>
              <ul className="divide-border divide-y">
                {rows
                  .filter((item) => item.group === group)
                  .map((item) => (
                    <li key={item.id} className="py-2">
                      <button
                        type="button"
                        disabled={busy || loading}
                        className="text-ink hover:bg-selected-bg w-full rounded px-2 py-1 text-left text-sm font-medium"
                        onClick={() => choose(item)}
                      >
                        {title(item)}
                      </button>
                      <p className="text-muted-ink px-2 text-xs leading-5">
                        {t("applicability")}: {label(item.applicability)}
                      </p>
                      <dl className="grid gap-x-3 px-2 text-xs leading-5 sm:grid-cols-2">
                        {[
                          "collection",
                          "digitalReview",
                          "physicalOriginal",
                          "currency",
                          "consistency",
                        ].map((field) => (
                          <div key={field}>
                            <dt className="text-muted-ink inline">
                              {t(field)}:{" "}
                            </dt>
                            <dd className="inline">
                              {label(
                                String(
                                  item[field as keyof ApiChecklistItemState],
                                ),
                              )}
                            </dd>
                          </div>
                        ))}
                      </dl>
                      {item.computedResolution === "SATISFIED" && (
                        <p className="text-forest px-2 text-xs">
                          {t("satisfied")}
                        </p>
                      )}
                    </li>
                  ))}
              </ul>
            </section>
          ))}
        </div>
        {selected ? (
          <div className="border-border space-y-4 border-t pt-4 xl:border-l xl:border-t-0 xl:pl-4 xl:pt-0">
            <h3 ref={selectedHeading} tabIndex={-1} className="font-semibold">
              {title(selected)}
            </h3>
            {selected.explanationKey && (
              <p className="text-muted-ink text-sm">
                {root.has(selected.explanationKey)
                  ? root(selected.explanationKey)
                  : humanizeMessageKey(selected.explanationKey)}
              </p>
            )}
            <p className="text-muted-ink text-sm">
              {t("applicability")}: {label(selected.applicability)}
            </p>
            <p className="text-muted-ink text-xs">
              {t("version", { version: selected.version })}
            </p>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              {[
                "collection",
                "digitalReview",
                "physicalOriginal",
                "currency",
                "consistency",
              ].map((field) => (
                <div key={field}>
                  <dt className="text-muted-ink">{t(field)}</dt>
                  <dd>
                    {label(
                      String(selected[field as keyof ApiChecklistItemState]),
                    )}
                  </dd>
                </div>
              ))}
            </dl>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void renew()}
            >
              {t("renew")}
            </Button>
            {
              <div className="space-y-3">
                <label className="block text-sm" htmlFor={`${id}-document`}>
                  {t("document")}
                </label>
                <select
                  id={`${id}-document`}
                  className={control}
                  value={document?.id ?? ""}
                  disabled={busy || stale || inboxError}
                  onChange={(event) =>
                    setDocument(
                      documents.find((row) => row.id === event.target.value) ??
                        null,
                    )
                  }
                >
                  <option value="">{t("chooseDocument")}</option>
                  {documents
                    .filter(
                      (row) =>
                        selected.acceptedDocumentClassIds.length === 0 ||
                        selected.acceptedDocumentClassIds.includes(
                          row.classId ?? "",
                        ),
                    )
                    .map((row) => (
                      <option key={row.id} value={row.id}>
                        {humanizeMessageKey(row.classId ?? "document")} &middot;{" "}
                        {row.id}
                      </option>
                    ))}
                </select>
                {document && (
                  <Link
                    className="text-link text-sm underline"
                    href={`/matters/${matterId}/documents/${document.id}/review`}
                  >
                    {t("viewDocument")}
                  </Link>
                )}
                <Button
                  disabled={
                    busy ||
                    inboxError ||
                    stale ||
                    !document ||
                    !document.interpretationGeneration
                  }
                  onClick={() =>
                    document &&
                    void save("links", {
                      detectedDocumentId: document.id,
                      documentVersion: document.version,
                      interpretationGeneration:
                        document.interpretationGeneration,
                    })
                  }
                >
                  {t("link")}
                </Button>
              </div>
            }
            {mode === "checks" && (
              <>
                {selected.physicalOriginalPolicy !== "NOT_REQUIRED" && (
                  <div className="space-y-3">
                    <label className="block text-sm" htmlFor={`${id}-method`}>
                      {t("method")}
                    </label>
                    <input
                      id={`${id}-method`}
                      className={control}
                      value={method}
                      maxLength={128}
                      onChange={(event) => setMethod(event.target.value)}
                      disabled={busy || stale}
                    />
                    <Button
                      disabled={
                        busy ||
                        stale ||
                        !method.trim() ||
                        selected.liveLinkCount === 0
                      }
                      onClick={() =>
                        void save("original-inspection", {
                          method: method.trim(),
                        })
                      }
                    >
                      {t("inspect")}
                    </Button>
                    {selected.liveLinkCount === 0 && (
                      <p className="text-muted-ink text-sm">{t("linkFirst")}</p>
                    )}
                  </div>
                )}
                <div className="space-y-3">
                  <label className="block text-sm" htmlFor={`${id}-dimension`}>
                    {t("dimension")}
                  </label>
                  <select
                    id={`${id}-dimension`}
                    className={control}
                    value={dimension}
                    disabled={busy || stale}
                    onChange={(event) => {
                      setDimension(event.target.value);
                      setDecision("");
                    }}
                  >
                    {Object.entries(choices)
                      .filter(([, values]) => values.length)
                      .map(([field]) => (
                        <option value={field} key={field}>
                          {t(field)}
                        </option>
                      ))}
                  </select>
                  <label className="block text-sm" htmlFor={`${id}-decision`}>
                    {t("decision")}
                  </label>
                  <select
                    id={`${id}-decision`}
                    className={control}
                    value={decision}
                    disabled={busy || stale}
                    onChange={(event) => setDecision(event.target.value)}
                  >
                    <option value="">{t("chooseDecision")}</option>
                    {(choices[dimension] ?? []).map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </select>
                  <label className="block text-sm" htmlFor={`${id}-reason`}>
                    {t("reason")}
                  </label>
                  <textarea
                    id={`${id}-reason`}
                    className={control}
                    value={reason}
                    disabled={busy || stale}
                    onChange={(event) => setReason(event.target.value)}
                  />
                  <Button
                    disabled={
                      busy ||
                      stale ||
                      !decision ||
                      (dimension === "applicability" && !reason.trim())
                    }
                    onClick={() =>
                      void save("decisions", {
                        [dimension]: decision,
                        ...(reason.trim() ? { reason: reason.trim() } : {}),
                      })
                    }
                  >
                    {t("saveDecision")}
                  </Button>
                </div>
              </>
            )}
            <details className="text-sm">
              <summary>{t("history")}</summary>
              {(selected.inspectionHistory ?? []).map((entry, index) => (
                <p
                  className="my-2 break-words"
                  key={`${entry.inspectedAt}-${index}`}
                >
                  {entry.method} &middot; {entry.reviewerId} &middot;{" "}
                  {entry.inspectedAt}
                  {entry.originals.map((source) => (
                    <span
                      className="block"
                      key={`${source.sourceFileId}-${source.storageVersion}`}
                    >
                      {source.sourceFileId} &middot; {source.storageVersion}{" "}
                      &middot; {source.sha256}
                    </span>
                  ))}
                </p>
              ))}
              {links.map((link) => (
                <p key={link.id} className="my-2 break-words">
                  <Link
                    className="text-link underline"
                    href={`/matters/${matterId}/documents/${link.detectedDocumentId}/review`}
                  >
                    {t("viewDocument")}
                  </Link>{" "}
                  &middot; {label(link.digitalReview)} &middot;{" "}
                  {t(link.isLive ? "liveEvidence" : "historicalEvidence")}{" "}
                  &middot;{" "}
                  {t("version", { version: link.documentVersion ?? 0 })}
                </p>
              ))}
            </details>
          </div>
        ) : !loading && rows.length > 0 ? (
          <div className="border-border flex items-center justify-center border-t px-4 py-8 xl:border-l xl:border-t-0">
            <p className="text-muted-ink max-w-xs text-center text-sm leading-6">
              {t("selectRequirement")}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
