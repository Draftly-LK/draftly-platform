"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Button } from "@/components/ui/button";
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
}: {
  matterId: string;
  getToken: TokenProvider;
  mode: "documents" | "checks";
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
  const pending = useRef<ManualIntent | null>(null);
  const title = (item: ApiChecklistItemState) =>
    root.has(item.labelKey)
      ? root(item.labelKey)
      : humanizeMessageKey(item.labelKey);
  const load = useCallback(async () => {
    const [next, inbox] = await Promise.all([
      getChecklist(getToken, matterId),
      getCompleteDocumentInbox(getToken, matterId),
    ]);
    setChecklist(next);
    setDocuments(inbox.documents);
    return next;
  }, [getToken, matterId]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    load()
      .catch((cause: unknown) => {
        if (alive) setError(apiErrorMessage(cause, t("unavailable")));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
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
    setSelected(item);
    setDocument(null);
    setMethod("");
    setDecision("");
    setReason("");
    setStale(false);
    setError(null);
  };
  const renew = async () => {
    if (pending.current) clearManualIntent(pending.current);
    pending.current = null;
    setBusy(true);
    try {
      if (selected) {
        const actor = await getMe(getToken);
        for (const operation of ["links", "decisions", "original-inspection"])
          clearPendingOperationIntent(
            actor.id,
            matterId,
            `requirement:${selected.id}:${operation}`,
          );
      }
      const fresh = await load();
      const item = fresh.items.find((row) => row.id === selected?.id);
      if (item) choose(item);
      else setSelected(null);
    } catch (cause) {
      setError(apiErrorMessage(cause, t("unavailable")));
    } finally {
      setBusy(false);
    }
  };
  const save = async (
    operation: RequirementOperation,
    body: Record<string, unknown>,
  ) => {
    if (!selected || stale) return;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      const actor = await getMe(getToken);
      const intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `requirement:${selected.id}:${operation}`,
        body,
        selected.version,
      );
      pending.current = intent;
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
      setSelected(null);
      setDocument(null);
      setNotice(t("saved"));
      await load();
    } catch (cause) {
      const changed =
        cause instanceof ApiError && [409, 412].includes(cause.status);
      setStale(changed);
      setError(
        changed ? t("changed") : apiErrorMessage(cause, t("saveFailed")),
      );
    } finally {
      setBusy(false);
    }
  };
  const rows = (checklist?.items ?? []).filter(
    (item) =>
      item.lifecycle !== "NOT_TRIGGERED" &&
      (mode === "checks" || item.computedResolution !== "SATISFIED"),
  );
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
      <p className="text-muted-ink text-sm leading-6">{t("notice")}</p>
      {loading && <p role="status">{t("loading")}</p>}
      {error && (
        <p className="text-red text-sm" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="text-muted-ink text-sm" role="status">
          {notice}
        </p>
      )}
      {!loading && checklist && rows.length === 0 && <p>{t("empty")}</p>}
      <div className="grid gap-4 xl:grid-cols-2">
        <ul className="divide-border max-h-80 divide-y overflow-y-auto">
          {rows.map((item) => (
            <li key={item.id} className="py-2">
              <button
                type="button"
                className="text-ink hover:bg-selected-bg w-full rounded px-2 py-1 text-left text-sm font-medium"
                onClick={() => choose(item)}
              >
                {title(item)}
              </button>
              <p className="text-muted-ink px-2 text-xs leading-5">
                {label(item.collection)} &middot; {label(item.digitalReview)}{" "}
                &middot; {label(item.physicalOriginal)}
              </p>
            </li>
          ))}
        </ul>
        {selected && (
          <div className="border-border space-y-4 border-t pt-4 xl:border-l xl:border-t-0 xl:pl-4 xl:pt-0">
            <h3 className="font-semibold">{title(selected)}</h3>
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
            {mode === "documents" && (
              <div className="space-y-3">
                <label className="block text-sm" htmlFor={`${id}-document`}>
                  {t("document")}
                </label>
                <select
                  id={`${id}-document`}
                  className={control}
                  value={document?.id ?? ""}
                  disabled={busy || stale}
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
            )}
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
                  ? {label(link.digitalReview)} &middot;{" "}
                  {t("version", { version: link.documentVersion ?? 0 })}
                </p>
              ))}
            </details>
          </div>
        )}
      </div>
    </section>
  );
}
