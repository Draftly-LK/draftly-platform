"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, type TokenProvider } from "@/lib/api/client";
import {
  getMatterFact,
  getFactHistory,
  reviewMatterFact,
} from "@/lib/api/facts";
import { getMe } from "@/lib/api/auth";
import {
  pendingOperationIntent,
  clearManualIntent,
  clearPendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import type {
  ApiFactEvidenceInput,
  ApiFactHistory,
  ApiFactType,
  ApiMatterFact,
  ApiMatterSubject,
  ApiMatterTransaction,
  ApiSourceFile,
} from "@/types/rta";
import { EvidenceSelector, FactEvidence } from "./fact-evidence";
import {
  controlClass,
  factValue,
  inputValue,
  RegisterError,
  Status,
  useFactDisplayValue,
  ValueInput,
} from "./fact-register-common";

export function FactReviewPanel({
  matterId,
  initial,
  subjects,
  transactions,
  sources,
  definition,
  subjectLabel,
  getToken,
  onSaved,
  onErrorChange,
  sourceRevision,
}: {
  matterId: string;
  initial: ApiMatterFact;
  subjects: ApiMatterSubject[];
  transactions: ApiMatterTransaction[];
  sources: ApiSourceFile[];
  definition?: ApiFactType;
  subjectLabel: (subject: ApiMatterSubject) => string;
  getToken: TokenProvider;
  onSaved: (fact: ApiMatterFact) => void;
  onErrorChange?: (factId: string, error: unknown) => void;
  sourceRevision?: number;
}) {
  const t = useTranslations("factRegister");
  const root = useTranslations();
  const fmt = useFormatter();
  const displayValue = useFactDisplayValue();
  const roleLabel = useEnumLabel("factRegister.roles");
  const [fact, setFact] = useState(initial);
  const [history, setHistory] = useState<ApiFactHistory | null>(null);
  const [alternatives, setAlternatives] = useState<ApiMatterFact[]>([]);
  const [reason, setReason] = useState("");
  const [value, setValue] = useState(factValue(initial.value));
  const [subject, setSubject] = useState(initial.subjectId ?? "");
  const [transaction, setTransaction] = useState(initial.transactionId ?? "");
  const [evidence, setEvidence] = useState<ApiFactEvidenceInput>();
  const [resolve, setResolve] = useState(false);
  const [resolutionIds, setResolutionIds] = useState(initial.conflictFactIds);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    onErrorChange?.(initial.id, error);
    return () => onErrorChange?.(initial.id, null);
  }, [error, initial.id, onErrorChange]);
  const [historyError, setHistoryError] = useState<unknown>(null);
  const [alternativesError, setAlternativesError] = useState<unknown>(null);
  const [reviewReady, setReviewReady] = useState(false);
  const [renewal, setRenewal] = useState<{
    operation: string;
    target: string;
  } | null>(null);
  const generation = useRef({ value: 0 });
  const [retryUnavailable, setRetryUnavailable] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  useEffect(() => {
    panelRef.current?.focus();
  }, []);
  const verifyOwner = useCallback(
    (item: ApiMatterFact) => {
      if (item.matterId !== matterId) throw new Error("Foreign fact response");
      return item;
    },
    [matterId],
  );
  const loadAlternatives = useCallback(
    async (ids: string[]) => {
      if (ids.length > 100) throw new Error("Alternative limit exceeded");
      return Promise.all(
        ids.map((id) =>
          getMatterFact(getToken, matterId, id).then(verifyOwner),
        ),
      );
    },
    [getToken, matterId, verifyOwner],
  );
  const renew = useCallback(
    async (id: string) => {
      const run = ++generation.current.value;
      setLoading(true);
      setBusy(false);
      setHistoryBusy(false);
      setReviewReady(false);
      setError(null);
      setResolve(false);
      setAlternatives([]);
      setAlternativesError(null);
      setHistory(null);
      setHistoryError(null);
      try {
        const item = verifyOwner(await getMatterFact(getToken, matterId, id));
        if (run !== generation.current.value) return;
        setFact(item);
        setReviewReady(true);
        setValue(factValue(item.value));
        setSubject(item.subjectId ?? "");
        setTransaction(item.transactionId ?? "");
        setResolutionIds(item.conflictFactIds);
        setReason("");
        setEvidence(undefined);
        const results = await Promise.allSettled([
          loadAlternatives(item.conflictFactIds),
          getFactHistory(getToken, matterId, item.id, { limit: 100 }),
        ]);
        if (run !== generation.current.value) return;
        if (results[0].status === "fulfilled")
          setAlternatives(results[0].value);
        else setAlternativesError(results[0].reason);
        if (results[1].status === "fulfilled") {
          results[1].value.items.forEach(verifyOwner);
          setHistory(results[1].value);
        } else setHistoryError(results[1].reason);
      } catch (cause) {
        if (run === generation.current.value) setError(cause);
      } finally {
        if (run === generation.current.value) setLoading(false);
      }
    },
    [getToken, matterId, verifyOwner, loadAlternatives],
  );
  useEffect(() => {
    void renew(initial.id);
    const epoch = generation.current;
    return () => {
      epoch.value++;
    };
  }, [initial.id, renew, sourceRevision]);
  const active =
    reviewReady &&
    !renewal &&
    !["REJECTED", "SUPERSEDED"].includes(fact.status);
  const evidenceAvailable =
    !fact.evidenceStale && (fact.evidence.length > 0 || evidence !== undefined);
  const resolved =
    resolutionIds.length === 0 ||
    (resolve &&
      reason.trim().length > 0 &&
      alternatives.length === resolutionIds.length &&
      alternativesError === null);
  const canAccept =
    !loading &&
    !busy &&
    active &&
    fact.scopeToken !== null &&
    evidenceAvailable &&
    resolved &&
    error === null;
  // A refusal is visible and recoverable. It is not an optimistic promotion.
  const canRetry =
    !loading &&
    !busy &&
    active &&
    fact.scopeToken !== null &&
    evidenceAvailable &&
    resolved;
  const selectedTransaction = transactions.find((tx) => tx.id === transaction);
  const choices = subjects.filter(
    (s) =>
      (definition?.subject === "PARTY"
        ? s.kind === "party"
        : ["PARCEL", "TITLE"].includes(definition?.subject ?? "")
          ? s.kind === "parcel"
          : true) &&
      (!selectedTransaction ||
        (s.kind === "party"
          ? selectedTransaction.partyRoles.some(
              (role) => role.subjectId === s.id,
            )
          : selectedTransaction.parcelSubjectIds.includes(s.id))),
  );
  const scopeChanged =
    subject !== (fact.subjectId ?? "") ||
    transaction !== (fact.transactionId ?? "");
  async function decide(action: "accept" | "correct" | "reject" | "associate") {
    const run = generation.current.value;
    let intent: ManualIntent | undefined;
    setBusy(true);
    setError(null);
    const decision = {
      reason: reason.trim() || undefined,
      expectedScopeToken: fact.scopeToken ?? undefined,
      resolveFactIds: resolutionIds,
      evidence,
      ...(action === "correct" ? { value: inputValue(value, definition) } : {}),
    };
    const association = {
      reason: reason.trim(),
      subjectId: subject || null,
      transactionId: transaction || null,
    };
    const body = action === "associate" ? association : decision;
    try {
      const token = await getToken();
      const actorToken = async () => token;
      const actor = await getMe(actorToken);
      if (run !== generation.current.value) return;
      intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `fact:${fact.id}:${action}`,
        body,
        fact.version,
      );
      setRetryUnavailable(!intent.persistent);
      if (run !== generation.current.value) return;
      const key = intent.key;
      const expectedVersion = intent.expectedVersion ?? fact.version;
      const saved =
        action === "associate"
          ? await reviewMatterFact(
              actorToken,
              matterId,
              fact.id,
              action,
              association,
              expectedVersion,
              key,
            )
          : await reviewMatterFact(
              actorToken,
              matterId,
              fact.id,
              action,
              decision,
              expectedVersion,
              key,
            );
      verifyOwner(saved);
      clearManualIntent(intent);
      if (run !== generation.current.value) return;
      onSaved(saved);
      if (saved.id === fact.id) await renew(saved.id);
    } catch (cause) {
      if (run !== generation.current.value) return;
      if (cause instanceof ApiError && cause.status === 412) {
        if (intent && !intent.reused) clearManualIntent(intent);
        const current =
          typeof cause.details.currentFactId === "string"
            ? cause.details.currentFactId
            : fact.id;
        setRenewal({ operation: `fact:${fact.id}:${action}`, target: current });
        setReviewReady(false);
      } else if (
        cause instanceof ApiError &&
        cause.status === 409 &&
        Array.isArray(cause.details.conflictFactIds) &&
        cause.details.conflictFactIds.every((id) => typeof id === "string")
      ) {
        const ids = cause.details.conflictFactIds as string[];
        setResolutionIds(ids);
        setResolve(false);
        setError(cause);
        try {
          const peers = await loadAlternatives(ids);
          if (run === generation.current.value) setAlternatives(peers);
        } catch (error) {
          if (run === generation.current.value) setAlternativesError(error);
        }
      } else setError(cause);
    } finally {
      if (run === generation.current.value) setBusy(false);
    }
  }
  async function renewDecision() {
    if (!renewal) return;
    const run = generation.current.value;
    setBusy(true);
    try {
      const actor = await getMe(getToken);
      if (run !== generation.current.value) return;
      clearPendingOperationIntent(actor.id, matterId, renewal.operation);
      setRenewal(null);
      await renew(renewal.target);
    } catch (cause) {
      if (run === generation.current.value) setError(cause);
    } finally {
      if (run === generation.current.value) setBusy(false);
    }
  }
  async function moreHistory() {
    if (!history?.page.nextCursor) return;
    const run = generation.current.value;
    setHistoryBusy(true);
    setHistoryError(null);
    try {
      const next = await getFactHistory(getToken, matterId, fact.id, {
        limit: 100,
        cursor: history.page.nextCursor,
      });
      next.items.forEach(verifyOwner);
      if (run === generation.current.value)
        setHistory((old) =>
          old
            ? {
                items: [...old.items, ...next.items],
                decisions: [
                  ...old.decisions,
                  ...next.decisions.filter(
                    (d) => !old.decisions.some((prior) => prior.id === d.id),
                  ),
                ],
                page: next.page,
              }
            : next,
        );
    } catch (cause) {
      if (run === generation.current.value) setHistoryError(cause);
    } finally {
      if (run === generation.current.value) setHistoryBusy(false);
    }
  }
  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      aria-label={t("reviewPanel")}
      className="border-border bg-canvas min-w-0 space-y-4 border-t p-4"
    >
      {loading && (
        <p role="status" className="flex gap-2 text-sm">
          <LoaderCircle
            aria-hidden="true"
            className="size-4 animate-spin motion-reduce:animate-none"
          />
          {t("loadingReview")}
        </p>
      )}

      {renewal && (
        <Button disabled={busy || loading} onClick={() => void renewDecision()}>
          {t("refresh")}
        </Button>
      )}
      {error != null && <RegisterError cause={error} />}
      {retryUnavailable && (
        <p role="status" className="text-amber-text text-sm">
          {t("retryStorageUnavailable")}
        </p>
      )}
      <div className="grid min-w-0 gap-4 xl:grid-cols-2">
        <div className="min-w-0 space-y-4">
          <dl className="grid min-w-0 grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-muted-ink">{t("originalValue")}</dt>
              <dd className="whitespace-pre-wrap break-words font-medium">
                {displayValue(fact.originalValue, definition)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-ink">{t("currentValue")}</dt>
              <dd className="whitespace-pre-wrap break-words font-medium">
                {displayValue(fact.value, definition)}
              </dd>
            </div>
          </dl>
          <Status fact={fact} />
          <p className="text-muted-ink text-xs">
            {t(`origin.${fact.origin}`)} ·{" "}
            {t("version", { number: fact.version })}
            {fact.modelReportedConfidence !== null && (
              <>
                {" "}
                ·{" "}
                {t("modelConfidence", {
                  value: fmt.number(fact.modelReportedConfidence, {
                    style: "percent",
                  }),
                })}
              </>
            )}
          </p>
          {fact.manualReason && (
            <p className="break-words text-sm">
              {t("manualReason")}: {fact.manualReason}
            </p>
          )}
          {fact.reviewedBy && (
            <p className="text-muted-ink break-words text-xs">
              {t("reviewer", { actor: fact.reviewedBy })}
              {fact.reviewedAt && (
                <>
                  {" "}
                  ·{" "}
                  {fmt.dateTime(new Date(fact.reviewedAt), {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </>
              )}
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              {t("factSubject")}
              <select
                className={controlClass}
                value={subject}
                disabled={loading || busy || !active}
                onChange={(e) => setSubject(e.target.value)}
              >
                <option value="">{t("chooseSubject")}</option>
                {choices.map((s) => (
                  <option key={s.id} value={s.id}>
                    {subjectLabel(s)}
                    {selectedTransaction?.partyRoles
                      .filter((r) => r.subjectId === s.id)
                      .map((r) => ` · ${roleLabel(r.role)}`)
                      .join("")}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              {t("factTransaction")}
              <select
                className={controlClass}
                value={transaction}
                disabled={loading || busy || !active}
                onChange={(e) => {
                  setTransaction(e.target.value);
                  setSubject("");
                }}
              >
                <option value="">{t("chooseTransaction")}</option>
                {transactions.map((tx) => (
                  <option key={tx.id} value={tx.id}>
                    {t("transactionNumber", { number: tx.ordinal })}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {fact.scopeStatus !== "assigned" && (
            <p className="text-amber-text text-sm">
              {t("associationRequired")}
            </p>
          )}
          <ValueInput
            label={t("correctedValue")}
            definition={definition}
            value={value}
            onChange={setValue}
            disabled={loading || busy || !active}
          />
          <label className="block text-sm font-medium">
            {t("reason")}
            <textarea
              className={controlClass}
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={busy || loading || !active}
            />
          </label>
          <details>
            <summary className="text-teal cursor-pointer text-sm">
              {t("attachEvidence")}
            </summary>
            <div className="mt-3">
              <EvidenceSelector
                sources={sources}
                value={evidence}
                onChange={setEvidence}
              />
            </div>
          </details>
          {!evidenceAvailable && (
            <p className="text-amber-text flex gap-2 text-sm">
              <AlertTriangle aria-hidden="true" className="size-4 shrink-0" />
              {t(fact.evidenceStale ? "staleEvidence" : "evidenceRequired")}
            </p>
          )}
          {resolutionIds.length > 0 && (
            <section className="border-amber bg-amber-bg space-y-3 rounded border p-3">
              <h4 className="text-amber-text flex gap-2 text-sm font-semibold">
                <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                {t("alternatives")}
              </h4>
              {alternativesError != null && (
                <RegisterError cause={alternativesError} />
              )}{" "}
              {alternatives.map((peer) => (
                <div key={peer.id} className="space-y-2 text-sm">
                  <p className="break-words font-medium">
                    {displayValue(peer.value, definition)}
                  </p>
                  <Status fact={peer} />
                  {peer.evidence.map((e) => (
                    <FactEvidence
                      key={e.id}
                      matterId={matterId}
                      evidence={e}
                      sources={sources}
                      getToken={getToken}
                    />
                  ))}
                </div>
              ))}
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1 shrink-0"
                  checked={resolve}
                  onChange={(e) => setResolve(e.target.checked)}
                  disabled={loading || busy || alternativesError !== null}
                />
                {t("resolveAlternatives")}
              </label>
            </section>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={
                loading ||
                busy ||
                !active ||
                !scopeChanged ||
                !definition ||
                (["PARTY", "PARCEL", "TITLE"].includes(definition.subject) &&
                  !subject) ||
                !transaction ||
                !reason.trim()
              }
              onClick={() => void decide("associate")}
            >
              {t("saveAssociation")}
            </Button>
            <Button
              variant="primary"
              disabled={!(error ? canRetry : canAccept) || scopeChanged}
              onClick={() => void decide("accept")}
            >
              {t("accept")}
            </Button>
            <Button
              disabled={
                !canRetry ||
                scopeChanged ||
                !reason.trim() ||
                !value.trim() ||
                !definition ||
                value === factValue(fact.value) ||
                (definition?.valueKind === "ENUM" &&
                  !definition.options?.length)
              }
              onClick={() => void decide("correct")}
            >
              {t("correct")}
            </Button>
            <Button
              disabled={loading || busy || !active || !reason.trim()}
              onClick={() => void decide("reject")}
            >
              {t("reject")}
            </Button>
          </div>
        </div>
        <div className="min-w-0 space-y-3">
          <h3 className="text-sm font-semibold">{t("supportingEvidence")}</h3>
          {fact.evidence.length === 0 && (
            <p className="text-muted-ink text-sm">{t("noEvidence")}</p>
          )}
          {fact.evidence.map((e) => (
            <FactEvidence
              key={e.id}
              matterId={matterId}
              evidence={e}
              sources={sources}
              getToken={getToken}
            />
          ))}
        </div>
      </div>
      <section className="border-border space-y-3 border-t pt-4">
        <h3 className="font-semibold">{t("history")}</h3>
        {historyError != null && <RegisterError cause={historyError} />}
        <ol className="space-y-3">
          {history?.decisions.map((d) => (
            <li
              key={d.id}
              className="border-border bg-surface min-w-0 rounded border p-3 text-sm"
            >
              <p className="flex flex-wrap gap-2 font-medium">
                {root.has(`factRegister.decisions.${d.decision}`)
                  ? root(`factRegister.decisions.${d.decision}`)
                  : t("decisionRecorded")}{" "}
                ·{" "}
                {fmt.dateTime(new Date(d.createdAt), {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </p>
              <p className="whitespace-pre-wrap break-words">
                {displayValue(d.previousValue, definition)} →{" "}
                {displayValue(d.newValue, definition)}
              </p>
              {d.reason && <p className="break-words">{d.reason}</p>}
              <p className="text-muted-ink break-words text-xs">
                {t("reviewer", { actor: d.reviewerId })}
              </p>
            </li>
          ))}
        </ol>
        {history?.page.hasMore && (
          <Button
            disabled={historyBusy || !history.page.nextCursor}
            onClick={() => void moreHistory()}
          >
            {t("moreHistory")}
          </Button>
        )}
      </section>
    </section>
  );
}
