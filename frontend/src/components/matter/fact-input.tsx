"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
  addManualFact,
  createSubject,
  saveTransaction,
  TRANSACTION_ROLES,
} from "@/lib/api/facts";
import { ApiError, type TokenProvider } from "@/lib/api/client";
import { getMe } from "@/lib/api/auth";
import {
  pendingManualIntent,
  pendingOperationIntent,
  clearManualIntent,
  clearPendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import type {
  ApiFactEvidenceInput,
  ApiDetectedDocument,
  ApiFactType,
  ApiMatterFact,
  ApiMatterSubject,
  ApiMatterTransaction,
  ApiSourceFile,
  TransactionRole,
} from "@/types/rta";
import {
  controlClass,
  inputValue,
  RegisterError,
  ValueInput,
} from "./fact-register-common";
import { EvidenceSelector } from "./fact-evidence";

export function ManualFactInput({
  matterId,
  documentContext,
  types,
  subjects,
  transactions,
  sources,
  subjectLabel,
  getToken,
  onSaved,
}: {
  matterId: string;
  documentContext?: ApiDetectedDocument;
  types: ApiFactType[];
  subjects: ApiMatterSubject[];
  transactions: ApiMatterTransaction[];
  sources: ApiSourceFile[];
  subjectLabel: (s: ApiMatterSubject) => string;
  getToken: TokenProvider;
  onSaved: (fact: ApiMatterFact) => void;
}) {
  const t = useTranslations("factRegister");
  const root = useTranslations();
  const [typeId, setTypeId] = useState("");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [subject, setSubject] = useState("");
  const [transaction, setTransaction] = useState("");
  const [evidence, setEvidence] = useState<ApiFactEvidenceInput>();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [retryUnavailable, setRetryUnavailable] = useState(false);
  const intent = useRef<ManualIntent | null>(null);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const definition = types.find((type) => type.id === typeId);
  const tx = transactions.find((t) => t.id === transaction);
  const eligible = subjects.filter(
    (s) =>
      (definition?.subject === "PARTY"
        ? s.kind === "party"
        : ["PARCEL", "TITLE"].includes(definition?.subject ?? "")
          ? s.kind === "parcel"
          : true) &&
      (!tx ||
        (s.kind === "party"
          ? tx.partyRoles.some((role) => role.subjectId === s.id)
          : tx.parcelSubjectIds.includes(s.id))),
  );
  async function save() {
    if (!definition) return;
    setBusy(true);
    setError(null);
    const body = {
      factTypeId: typeId,
      value: inputValue(value, definition),
      reason: reason.trim(),
      subjectId: subject || null,
      transactionId: transaction || null,
      evidence,
    };
    try {
      const actor = await getMe(getToken);
      if (!active.current) return;
      intent.current = await pendingManualIntent(actor.id, matterId, body);
      setRetryUnavailable(!intent.current.persistent);
      if (!active.current) return;
      const fact = await addManualFact(
        getToken,
        matterId,
        body,
        intent.current.key,
      );
      if (fact.matterId !== matterId) throw new Error("Foreign manual fact");
      clearManualIntent(intent.current);
      if (!active.current) return;
      onSaved(fact);
    } catch (cause) {
      if (active.current) setError(cause);
    } finally {
      if (active.current) setBusy(false);
    }
  }
  return (
    <section
      className="rounded-card border-border bg-surface space-y-4 border p-4"
      aria-label={t("manualTitle")}
    >
      <h2 className="font-semibold">{t("manualTitle")}</h2>
      <p className="text-muted-ink text-sm">{t("manualNotice")}</p>
      {error != null && <RegisterError cause={error} />}
      {retryUnavailable && (
        <p role="status" className="text-amber-text text-sm">
          {t("retryStorageUnavailable")}
        </p>
      )}
      {error != null && (
        <Button
          disabled={busy}
          onClick={() => {
            if (intent.current) clearManualIntent(intent.current);
            intent.current = null;
            setTypeId("");
            setValue("");
            setReason("");
            setSubject("");
            setTransaction("");
            setEvidence(undefined);
            setError(null);
          }}
        >
          {t("newManualIntent")}
        </Button>
      )}
      <label className="block text-sm font-medium">
        {t("factType")}
        <select
          className={controlClass}
          value={typeId}
          disabled={busy}
          onChange={(e) => {
            setTypeId(e.target.value);
            setValue("");
            setSubject("");
          }}
        >
          <option value="">{t("chooseFactType")}</option>
          {types.map((type) => (
            <option key={type.id} value={type.id}>
              {root.has(type.labelKey)
                ? root(type.labelKey)
                : t("unknownFactType")}
            </option>
          ))}
        </select>
      </label>
      <ValueInput
        definition={definition}
        value={value}
        onChange={setValue}
        label={t("manualValue")}
        disabled={!definition || busy}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">
          {t("factTransaction")}
          <select
            className={controlClass}
            value={transaction}
            disabled={busy}
            onChange={(e) => {
              setTransaction(e.target.value);
              setSubject("");
            }}
          >
            <option value="">{t("saveUnassigned")}</option>
            {transactions.map((tx) => (
              <option key={tx.id} value={tx.id}>
                {t("transactionNumber", { number: tx.ordinal })}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          {t("factSubject")}
          <select
            className={controlClass}
            value={subject}
            disabled={busy}
            onChange={(e) => setSubject(e.target.value)}
          >
            <option value="">{t("saveUnassigned")}</option>
            {eligible.map((s) => (
              <option key={s.id} value={s.id}>
                {subjectLabel(s)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="block text-sm font-medium">
        {t("manualReason")}
        <textarea
          className={controlClass}
          value={reason}
          maxLength={2000}
          disabled={busy}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <EvidenceSelector
        documentContext={documentContext}
        sources={sources}
        value={evidence}
        onChange={setEvidence}
      />
      <Button
        variant="primary"
        disabled={
          busy ||
          !definition ||
          (definition.valueKind === "ENUM" && !definition.options?.length) ||
          (evidence &&
            documentContext &&
            evidence.detectedDocumentId === documentContext.id &&
            (documentContext.versionRelationship === "SUPERSEDED" ||
              evidence.interpretationGeneration !==
                documentContext.interpretationGeneration ||
              !documentContext.fragments.some(
                (fragment) =>
                  fragment.sourceFileId === evidence.sourceFileId &&
                  fragment.pageStart <= evidence.pageNumber &&
                  fragment.pageEnd >= evidence.pageNumber,
              ))) ||
          !reason.trim() ||
          !value.trim()
        }
        onClick={() => void save()}
      >
        {t("saveManual")}
      </Button>
    </section>
  );
}

export function FactScopeInput({
  matterId,
  subjects,
  transactions,
  subjectLabel,
  getToken,
  onChanged,
  disabled = false,
}: {
  matterId: string;
  subjects: ApiMatterSubject[];
  transactions: ApiMatterTransaction[];
  subjectLabel: (s: ApiMatterSubject) => string;
  getToken: TokenProvider;
  onChanged: () => void;
  disabled?: boolean;
}) {
  const t = useTranslations("factRegister");
  const roleLabel = useEnumLabel("factRegister.roles");
  const setupDetails = useRef<HTMLDetailsElement>(null);
  const setupSummary = useRef<HTMLElement>(null);
  useEffect(() => {
    function openSetup() {
      if (window.location.hash !== "#transaction-scope") return;
      if (setupDetails.current) setupDetails.current.open = true;
      setupSummary.current?.focus();
    }
    openSetup();
    window.addEventListener("hashchange", openSetup);
    return () => window.removeEventListener("hashchange", openSetup);
  }, []);
  const [current, setCurrent] = useState("");
  const [reviewedTransaction, setReviewedTransaction] =
    useState<ApiMatterTransaction>();
  const transactionSelect = useRef<HTMLSelectElement>(null);
  const [parcels, setParcels] = useState<string[]>([]);
  const [roles, setRoles] = useState<Record<string, TransactionRole | "">>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [stale, setStale] = useState(false);
  const scopeEpoch = useRef(0);
  const pendingScopeFocus = useRef<{
    epoch: number;
    transactionId: string;
    version: number;
  } | null>(null);
  const [retryUnavailable, setRetryUnavailable] = useState(false);
  const selectedTransaction = transactions.find((tx) => tx.id === current);
  const scopeOutdated = Boolean(
    current &&
      (!reviewedTransaction ||
        !selectedTransaction ||
        reviewedTransaction.id !== current ||
        reviewedTransaction.version !== selectedTransaction.version),
  );
  function reviewTransaction(tx?: ApiMatterTransaction) {
    pendingScopeFocus.current = null;
    setReviewedTransaction(tx);
    setParcels(tx?.parcelSubjectIds ?? []);
    setRoles(
      Object.fromEntries(
        tx?.partyRoles.map((role) => [role.subjectId, role.role]) ?? [],
      ),
    );
    setStale(false);
  }
  useEffect(() => {
    const epoch = scopeEpoch;
    return () => {
      epoch.current++;
      pendingScopeFocus.current = null;
    };
  }, [getToken, matterId]);
  useEffect(() => {
    if (busy) return;
    const pending = pendingScopeFocus.current;
    pendingScopeFocus.current = null;
    if (
      pending &&
      pending.epoch === scopeEpoch.current &&
      pending.transactionId === current &&
      pending.version === reviewedTransaction?.version &&
      !scopeOutdated &&
      !transactionSelect.current?.disabled
    )
      transactionSelect.current?.focus();
  }, [busy, current, reviewedTransaction?.version, scopeOutdated]);
  async function renewScope() {
    pendingScopeFocus.current = null;
    const run = scopeEpoch.current;
    const tx = selectedTransaction;
    if (!tx) return;
    setBusy(true);
    setError(null);
    try {
      const actor = await getMe(getToken);
      if (run !== scopeEpoch.current) return;
      clearPendingOperationIntent(actor.id, matterId, `transaction:${tx.id}`);
      reviewTransaction(tx);
      pendingScopeFocus.current = {
        epoch: run,
        transactionId: tx.id,
        version: tx.version,
      };
    } catch (cause) {
      if (run === scopeEpoch.current) setError(cause);
    } finally {
      if (run === scopeEpoch.current) setBusy(false);
    }
  }
  async function addSubject(kind: "party" | "parcel") {
    pendingScopeFocus.current = null;
    const run = scopeEpoch.current;
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const actorToken = async () => token;
      const actor = await getMe(actorToken);
      if (run !== scopeEpoch.current) return;
      const intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `subject:create:${kind}`,
        { kind },
      );
      setRetryUnavailable(!intent.persistent);
      if (run !== scopeEpoch.current) return;
      const result = await createSubject(
        actorToken,
        matterId,
        kind,
        intent.key,
      );
      if (result.matterId !== matterId) throw new Error("Foreign subject");
      clearManualIntent(intent);
      if (run !== scopeEpoch.current) return;
      onChanged();
    } catch (cause) {
      if (run === scopeEpoch.current) setError(cause);
    } finally {
      if (run === scopeEpoch.current) setBusy(false);
    }
  }
  async function save() {
    pendingScopeFocus.current = null;
    const run = scopeEpoch.current;
    let intent: ManualIntent | undefined;
    if (scopeOutdated || stale || (current && !reviewedTransaction)) return;
    // This version belongs to the scope the lawyer actually reviewed. An
    // unresolved nonempty selection must never fall through to creation.
    const tx = current ? reviewedTransaction : undefined;
    const body = {
      parcelSubjectIds: [...parcels].sort(),
      partyRoles: Object.entries(roles)
        .sort(([a], [b]) => a.localeCompare(b))
        .flatMap(([subjectId, role]) => (role ? [{ subjectId, role }] : [])),
    };
    setBusy(true);
    setError(null);
    setStale(false);
    try {
      const token = await getToken();
      const actorToken = async () => token;
      const actor = await getMe(actorToken);
      if (run !== scopeEpoch.current) return;
      intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `transaction:${tx?.id ?? "create"}`,
        body,
        tx?.version,
      );
      setRetryUnavailable(!intent.persistent);
      if (run !== scopeEpoch.current) return;
      const result = await saveTransaction(
        actorToken,
        matterId,
        body,
        intent.key,
        tx
          ? { ...tx, version: intent.expectedVersion ?? tx.version }
          : undefined,
      );
      if (result.matterId !== matterId) throw new Error("Foreign transaction");
      clearManualIntent(intent);
      if (run !== scopeEpoch.current) return;
      setCurrent("");
      setReviewedTransaction(undefined);
      setParcels([]);
      setRoles({});
      onChanged();
    } catch (cause) {
      if (run !== scopeEpoch.current) return;
      if (cause instanceof ApiError && cause.status === 412) {
        if (intent && !intent.reused) clearManualIntent(intent);
        setStale(true);
        onChanged();
      } else setError(cause);
    } finally {
      if (run === scopeEpoch.current) setBusy(false);
    }
  }
  return (
    <details
      ref={setupDetails}
      id="transaction-scope"
      className="rounded-card border-border bg-surface space-y-4 border p-4"
    >
      <summary ref={setupSummary} className="cursor-pointer font-semibold">
        {t("scopeTitle")}
      </summary>
      <fieldset disabled={disabled} className="space-y-4 pt-4">
        <p className="text-muted-ink text-sm">{t("scopeNotice")}</p>
        {error != null && <RegisterError cause={error} />}
        {retryUnavailable && (
          <p role="status" className="text-amber-text text-sm">
            {t("retryStorageUnavailable")}
          </p>
        )}
        {(stale || scopeOutdated) && (
          <p role="status" className="text-amber-text text-sm">
            {t("staleReview")}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void addSubject("party")}>
            {t("addParty")}
          </Button>
          <Button disabled={busy} onClick={() => void addSubject("parcel")}>
            {t("addParcel")}
          </Button>
        </div>
        <label className="block text-sm font-medium">
          {t("editTransaction")}
          <select
            ref={transactionSelect}
            className={controlClass}
            value={current}
            disabled={busy}
            onChange={(e) => {
              const tx = transactions.find((tx) => tx.id === e.target.value);
              setCurrent(e.target.value);
              reviewTransaction(tx);
            }}
          >
            <option value="">{t("newTransaction")}</option>
            {current && !selectedTransaction && (
              <option value={current}>{t("scopeUnavailable")}</option>
            )}
            {transactions.map((tx) => (
              <option key={tx.id} value={tx.id}>
                {t("transactionNumber", { number: tx.ordinal })}
              </option>
            ))}
          </select>
        </label>
        {current && (stale || scopeOutdated) && (
          <Button
            disabled={busy || !selectedTransaction}
            onClick={() => void renewScope()}
          >
            {t("reviewTransaction")}
          </Button>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {subjects.map((s) =>
            s.kind === "parcel" ? (
              <label key={s.id} className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={parcels.includes(s.id)}
                  disabled={busy || stale || scopeOutdated}
                  className="mt-1"
                  onChange={(e) =>
                    setParcels((old) =>
                      e.target.checked
                        ? [...old, s.id]
                        : old.filter((id) => id !== s.id),
                    )
                  }
                />
                {subjectLabel(s)}
              </label>
            ) : (
              <label key={s.id} className="min-w-0 text-sm font-medium">
                {subjectLabel(s)}
                <select
                  className={controlClass}
                  value={roles[s.id] ?? ""}
                  disabled={busy || stale || scopeOutdated}
                  onChange={(e) =>
                    setRoles((old) => ({
                      ...old,
                      [s.id]: e.target.value as TransactionRole | "",
                    }))
                  }
                >
                  <option value="">{t("noRole")}</option>
                  {TRANSACTION_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {roleLabel(role)}
                    </option>
                  ))}
                </select>
              </label>
            ),
          )}
        </div>
        <Button
          variant="primary"
          disabled={
            busy ||
            stale ||
            scopeOutdated ||
            (!parcels.length && !Object.values(roles).some(Boolean))
          }
          onClick={() => void save()}
        >
          {t("saveTransaction")}
        </Button>
      </fieldset>
    </details>
  );
}
