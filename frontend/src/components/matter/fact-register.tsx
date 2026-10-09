"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { FileText, LoaderCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import {
  getFactTypes,
  listMatterFacts,
  listSubjects,
  listTransactions,
  type ApiFactPage,
} from "@/lib/api/facts";
import { listSourceFiles } from "@/lib/api/documents";
import type {
  ApiFactType,
  ApiMatterFact,
  ApiMatterSubject,
  ApiMatterTransaction,
  ApiSourceFile,
} from "@/types/rta";
import {
  controlClass,
  useFactDisplayValue,
  RegisterError,
  Status,
  subjectContext,
} from "./fact-register-common";
import { FactReviewPanel } from "./fact-review-panel";
import { FactScopeInput, ManualFactInput } from "./fact-input";

/** Resource menus are bounded. Partial data stays labelled and never implies all. */
async function references<T extends { matterId: string }>(
  matterId: string,
  read: (cursor?: string) => Promise<ApiFactPage<T>>,
) {
  const items: T[] = [];
  const seen = new Set<string>();
  let cursor: string | undefined;
  for (let page = 0; page < 10; page++) {
    const result = await read(cursor);
    if (result.items.some((item) => item.matterId !== matterId))
      throw new Error("Foreign reference response");
    items.push(...result.items);
    if (!result.page.hasMore) return { items, partial: false };
    if (!result.page.nextCursor || seen.has(result.page.nextCursor))
      return { items, partial: true };
    cursor = result.page.nextCursor;
    seen.add(cursor);
  }
  return { items, partial: true };
}
export function FactRegister(props: {
  matterId: string;
  documentId?: string;
  onDecision?: () => void;
  sourceRevision?: number;
}) {
  return (
    <RegisterContent
      key={`${props.matterId}:${props.documentId ?? "matter"}`}
      {...props}
    />
  );
}
function RegisterContent({
  matterId,
  documentId,
  onDecision,
  sourceRevision,
}: {
  matterId: string;
  documentId?: string;
  onDecision?: () => void;
  sourceRevision?: number;
}) {
  const t = useTranslations("factRegister");
  const root = useTranslations();
  const factsT = useTranslations("facts");
  const displayValue = useFactDisplayValue();
  const getToken = useTokenProvider();
  const [facts, setFacts] = useState<ApiMatterFact[]>([]);
  const [subjects, setSubjects] = useState<ApiMatterSubject[]>([]);
  const [transactions, setTransactions] = useState<ApiMatterTransaction[]>([]);
  const [sources, setSources] = useState<ApiSourceFile[]>([]);
  const [types, setTypes] = useState<ApiFactType[]>([]);
  const [loading, setLoading] = useState(true);
  const [moreBusy, setMoreBusy] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [resourceErrors, setResourceErrors] = useState<unknown[]>([]);
  const [referencePartial, setReferencePartial] = useState(false);
  const [factPartial, setFactPartial] = useState(false);
  const [selected, setSelected] = useState<ApiMatterFact | null>(null);
  const [subjectFilter, setSubjectFilter] = useState("");
  const [transactionFilter, setTransactionFilter] = useState("");
  const [manual, setManual] = useState(false);
  const generation = useRef({ value: 0 });
  const factRequest = useRef(0);
  const referenceRequest = useRef(0);
  const seenCursors = useRef(new Set<string>());
  const loadFacts = useCallback(
    async (append = false, nextCursor?: string) => {
      const run = generation.current.value;
      const request = ++factRequest.current;
      if (append) setMoreBusy(true);
      setError(null);
      try {
        const result = await listMatterFacts(getToken, matterId, {
          limit: 50,
          cursor: nextCursor,
        });
        if (run !== generation.current.value || request !== factRequest.current)
          return;
        if (result.items.some((f) => f.matterId !== matterId))
          throw new Error("Foreign fact response");
        setFacts((old) =>
          append
            ? [
                ...old,
                ...result.items.filter(
                  (f) => !old.some((item) => item.id === f.id),
                ),
              ]
            : result.items,
        );
        if (nextCursor) seenCursors.current.add(nextCursor);
        if (
          result.page.hasMore &&
          (!result.page.nextCursor ||
            seenCursors.current.has(result.page.nextCursor))
        ) {
          setCursor(null);
          setFactPartial(true);
        } else {
          setFactPartial(false);
          setCursor(result.page.hasMore ? result.page.nextCursor : null);
        }
      } catch (cause) {
        if (run === generation.current.value && request === factRequest.current)
          setError(cause);
      } finally {
        if (
          run === generation.current.value &&
          request === factRequest.current
        ) {
          setLoading(false);
          setMoreBusy(false);
        }
      }
    },
    [getToken, matterId],
  );
  const loadResources = useCallback(async () => {
    const run = generation.current.value;
    const request = ++referenceRequest.current;
    const results = await Promise.allSettled([
      references(matterId, (cursor) =>
        listSubjects(getToken, matterId, { limit: 100, cursor }),
      ),
      references(matterId, (cursor) =>
        listTransactions(getToken, matterId, { limit: 100, cursor }),
      ),
      references(matterId, (cursor) =>
        listSourceFiles(getToken, matterId, { limit: 100, cursor }),
      ),
      getFactTypes(getToken),
    ]);
    if (
      run !== generation.current.value ||
      request !== referenceRequest.current
    )
      return;
    const errors: unknown[] = [];
    let partial = false;
    if (results[0].status === "fulfilled") {
      setSubjects(results[0].value.items);
      partial ||= results[0].value.partial;
    } else {
      setSubjects([]);
      errors.push(results[0].reason);
    }
    if (results[1].status === "fulfilled") {
      setTransactions(results[1].value.items);
      partial ||= results[1].value.partial;
    } else {
      setTransactions([]);
      errors.push(results[1].reason);
    }
    if (results[2].status === "fulfilled") {
      setSources(results[2].value.items);
      partial ||= results[2].value.partial;
    } else {
      setSources([]);
      errors.push(results[2].reason);
    }
    if (results[3].status === "fulfilled") setTypes(results[3].value.factTypes);
    else {
      setTypes([]);
      errors.push(results[3].reason);
    }
    setResourceErrors(errors);
    setReferencePartial(partial);
  }, [getToken, matterId]);
  useEffect(() => {
    const epoch = generation.current;
    setLoading(true);
    void loadFacts();
    void loadResources();
    return () => {
      epoch.value++;
    };
  }, [loadFacts, loadResources, sourceRevision]);
  const subjectLabel = (subject: ApiMatterSubject) =>
    `${t(subject.kind === "party" ? "partyNumber" : "parcelNumber", { number: subject.ordinal })}${subjectContext(subject, facts) ? ` · ${subjectContext(subject, facts)}` : ""}`;
  const subjectName = (id: string | null) =>
    subjects.find((s) => s.id === id)
      ? subjectLabel(subjects.find((s) => s.id === id)!)
      : t(id ? "scopeUnavailable" : "unassigned");
  const transactionName = (id: string | null) =>
    transactions.find((tx) => tx.id === id)
      ? t("transactionNumber", {
          number: transactions.find((tx) => tx.id === id)!.ordinal,
        })
      : t(id ? "scopeUnavailable" : "unassigned");
  function saved(fact: ApiMatterFact) {
    onDecision?.();
    setSelected(fact);
    setManual(false);
    setFacts((old) => [
      fact,
      ...old.filter((f) => f.id !== fact.id && f.id !== selected?.id),
    ]);
    seenCursors.current.clear();
    void loadFacts();
  }
  const shown = facts.filter(
    (f) =>
      (!subjectFilter ||
        (subjectFilter === "unassigned"
          ? !f.subjectId
          : f.subjectId === subjectFilter)) &&
      (!transactionFilter || f.transactionId === transactionFilter) &&
      (!documentId ||
        f.evidence.some((e) => e.detectedDocumentId === documentId)),
  );
  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted-ink max-w-3xl text-sm">
          {t("registerNotice")}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => {
              generation.current.value++;
              seenCursors.current.clear();
              setSelected(null);
              setFacts([]);
              setLoading(true);
              void loadFacts();
              void loadResources();
            }}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            {t("refresh")}
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              setSelected(null);
              setManual((old) => !old);
            }}
            aria-expanded={manual}
          >
            {t("addManual")}
          </Button>
        </div>
      </div>
      {error != null && <RegisterError cause={error} />}
      {resourceErrors.length > 0 && (
        <div className="space-y-2">
          <p className="text-muted-ink text-sm">{t("referencesUnavailable")}</p>
          <RegisterError cause={resourceErrors[0]} />
        </div>
      )}
      {referencePartial && (
        <p role="status" className="text-amber-text text-sm">
          {t("partialReferences")}
        </p>
      )}
      {factPartial && (
        <p role="status" className="text-amber-text text-sm">
          {t("partialFacts")}
        </p>
      )}
      {manual && (
        <ManualFactInput
          matterId={matterId}
          types={types}
          subjects={subjects}
          transactions={transactions}
          sources={sources}
          subjectLabel={subjectLabel}
          getToken={getToken}
          onSaved={saved}
        />
      )}
      <FactScopeInput
        matterId={matterId}
        subjects={subjects}
        transactions={transactions}
        subjectLabel={subjectLabel}
        getToken={getToken}
        onChanged={() => void loadResources()}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">
          {t("subjectFilter")}
          <select
            className={controlClass}
            value={subjectFilter}
            onChange={(e) => setSubjectFilter(e.target.value)}
          >
            <option value="">{t("allSubjects")}</option>
            <option value="unassigned">{t("unassigned")}</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {subjectLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          {t("transactionFilter")}
          <select
            className={controlClass}
            value={transactionFilter}
            onChange={(e) => setTransactionFilter(e.target.value)}
          >
            <option value="">{t("allTransactions")}</option>
            {transactions.map((tx) => (
              <option key={tx.id} value={tx.id}>
                {t("transactionNumber", { number: tx.ordinal })}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-muted-ink text-xs">
        {t("loadedFacts", { count: facts.length })}
        {cursor && <> · {t("moreAvailable")}</>}
      </p>
      {loading && (
        <p role="status" className="flex items-center justify-center gap-2 p-6">
          <LoaderCircle
            className="size-5 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          {t("loading")}
        </p>
      )}
      {!loading && shown.length === 0 && error === null && (
        <div className="rounded-card border-border bg-surface border p-6 text-center">
          <FileText
            className="text-muted-ink mx-auto size-6"
            aria-hidden="true"
          />
          <p className="mt-2 text-sm">{t("empty")}</p>
        </div>
      )}
      <div className="space-y-3">
        {shown.map((fact) => (
          <article
            key={fact.id}
            className="rounded-card border-border bg-surface min-w-0 overflow-hidden border"
          >
            <div className="flex flex-wrap items-start justify-between gap-3 p-4">
              <div className="min-w-0 flex-1 basis-72">
                <h2 className="break-words text-sm font-semibold">
                  {root.has(fact.labelKey)
                    ? root(fact.labelKey)
                    : t("unknownFactType")}
                </h2>
                <p className="mt-1 whitespace-pre-wrap break-words font-medium">
                  {displayValue(
                    fact.value,
                    types.find((type) => type.id === fact.factTypeId),
                  )}
                </p>
                <p className="text-muted-ink mt-2 break-words text-xs">
                  {subjectName(fact.subjectId)} ·{" "}
                  {transactionName(fact.transactionId)}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Status fact={fact} />
                <Button
                  aria-expanded={selected?.id === fact.id}
                  onClick={() =>
                    setSelected((old) => (old?.id === fact.id ? null : fact))
                  }
                >
                  {selected?.id === fact.id
                    ? factsT("closeReview")
                    : factsT("reviewFact")}
                </Button>
              </div>
            </div>
            {selected?.id === fact.id && (
              <FactReviewPanel
                key={selected.id}
                matterId={matterId}
                initial={selected}
                sourceRevision={sourceRevision}
                subjects={subjects}
                transactions={transactions}
                sources={sources}
                definition={types.find(
                  (type) => type.id === selected.factTypeId,
                )}
                subjectLabel={subjectLabel}
                getToken={getToken}
                onSaved={saved}
              />
            )}
          </article>
        ))}
      </div>
      {selected && !shown.some((f) => f.id === selected.id) && (
        <FactReviewPanel
          key={selected.id}
          matterId={matterId}
          initial={selected}
          subjects={subjects}
          transactions={transactions}
          sources={sources}
          definition={types.find((type) => type.id === selected.factTypeId)}
          subjectLabel={subjectLabel}
          getToken={getToken}
          onSaved={saved}
        />
      )}
      {cursor && (
        <Button
          disabled={moreBusy}
          onClick={() => void loadFacts(true, cursor)}
        >
          {t("moreFacts")}
        </Button>
      )}
    </div>
  );
}
