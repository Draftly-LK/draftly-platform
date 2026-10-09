"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { listTransactions, listSubjects } from "@/lib/api/facts";
import type { TokenProvider } from "@/lib/api/client";
import type { RunChecksBody } from "@/lib/api/checks";
import type { ApiMatterTransaction, ApiMatterSubject } from "@/types/rta";
import { FactScopeInput } from "@/components/matter/fact-input";
import {
  MATTER_WORK_CHANGED,
  notifyMatterWorkChanged,
} from "@/lib/matter-work-events";
export function CheckScopeSelector({
  matterId,
  getToken,
  value,
  onChange,
  disabled = false,
}: {
  matterId: string;
  getToken: TokenProvider;
  value: RunChecksBody | null;
  onChange: (scope: RunChecksBody | null) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("checkScope");
  const id = useId();
  const [transactions, setTransactions] = useState<ApiMatterTransaction[]>([]);
  const [subjects, setSubjects] = useState<ApiMatterSubject[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const epoch = useRef(0);
  const load = useCallback(async () => {
    const run = ++epoch.current;
    onChange(null);
    setLoading(true);
    setError(false);
    try {
      const all: ApiMatterTransaction[] = [];
      let cursor: string | undefined;
      const seen = new Set<string>();
      do {
        const page = await listTransactions(getToken, matterId, {
          limit: 100,
          cursor,
        });
        all.push(...page.items);
        cursor = page.page.nextCursor ?? undefined;
        if (cursor && seen.has(cursor)) throw new Error("Repeated page");
        if (cursor) seen.add(cursor);
      } while (cursor && seen.size < 100);
      if (cursor) throw new Error("Incomplete scope");
      const allSubjects: ApiMatterSubject[] = [];
      cursor = undefined;
      seen.clear();
      do {
        const page = await listSubjects(getToken, matterId, {
          limit: 100,
          cursor,
        });
        allSubjects.push(...page.items);
        cursor = page.page.nextCursor ?? undefined;
        if (cursor && seen.has(cursor))
          throw new Error("Repeated subject page");
        if (cursor) seen.add(cursor);
      } while (cursor && seen.size < 100);
      if (cursor) throw new Error("Incomplete subjects");
      if (
        all.some((row) =>
          [
            ...row.parcelSubjectIds,
            ...row.partyRoles.map((role) => role.subjectId),
          ].some((subject) => !allSubjects.some((item) => item.id === subject)),
        )
      )
        throw new Error("Missing subject reference");
      if (run !== epoch.current) return;
      setTransactions(all);
      setSubjects(allSubjects);
      setError(false);
    } catch {
      if (run !== epoch.current) return;
      setError(true);
      onChange(null);
    } finally {
      if (run === epoch.current) setLoading(false);
    }
  }, [getToken, matterId, onChange]);
  useEffect(() => {
    const generation = epoch;
    void load();
    const refresh = (event: Event) => {
      if (
        (event as CustomEvent<{ matterId: string }>).detail?.matterId ===
        matterId
      )
        void load();
    };
    window.addEventListener(MATTER_WORK_CHANGED, refresh);
    return () => {
      generation.current++;
      window.removeEventListener(MATTER_WORK_CHANGED, refresh);
    };
  }, [load, matterId]);
  const selected = transactions.find((row) => row.id === value?.transactionId);
  const stale = value && selected?.version !== value.associationVersion;
  useEffect(() => {
    if (stale) onChange(null);
  }, [stale, onChange]);
  const control =
    "border-border-control bg-surface rounded-control min-h-10 w-full border px-3 py-2 text-sm";
  return (
    <section
      className="border-border my-6 space-y-3 border-b pb-5"
      aria-labelledby={`${id}-title`}
    >
      <h2 id={`${id}-title`} className="text-lg font-semibold">
        {t("title")}
      </h2>
      <p className="text-muted-ink text-sm">{t("notice")}</p>
      {loading && (
        <p role="status" className="text-muted-ink text-sm">
          {t("loading")}
        </p>
      )}
      {!loading && !error && transactions.length === 0 && (
        <p className="text-muted-ink text-sm">{t("empty")}</p>
      )}
      <FactScopeInput
        key={matterId}
        matterId={matterId}
        getToken={getToken}
        subjects={subjects}
        transactions={transactions}
        subjectLabel={(subject) =>
          `${t(subject.kind === "parcel" ? "parcelNumber" : "partyNumber", { number: subject.ordinal })} · ${subject.id}`
        }
        onChanged={() => notifyMatterWorkChanged(matterId)}
        disabled={disabled || loading || error}
      />
      {error && (
        <p role="alert" className="text-red">
          {t("unavailable")}
        </p>
      )}
      {stale && (
        <p role="alert" className="text-red">
          {t("changed")}
        </p>
      )}
      <div className="grid gap-3 xl:grid-cols-2">
        <label className="space-y-1 text-sm" htmlFor={`${id}-transaction`}>
          {t("transaction")}
          <select
            id={`${id}-transaction`}
            className={control}
            disabled={disabled || loading || error}
            value={value?.transactionId ?? ""}
            onChange={(event) => {
              const row = transactions.find(
                (item) => item.id === event.target.value,
              );
              onChange(
                row
                  ? {
                      transactionId: row.id,
                      associationVersion: row.version,
                      subjectId: null,
                    }
                  : null,
              );
            }}
          >
            <option value="">{t("choose")}</option>
            {transactions.map((row) => (
              <option value={row.id} key={row.id}>
                {t("transactionNumber", { number: row.ordinal })}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm" htmlFor={`${id}-subject`}>
          {t("subject")}
          <select
            id={`${id}-subject`}
            className={control}
            disabled={disabled || loading || error || !selected || !!stale}
            value={value?.subjectId ?? ""}
            onChange={(event) => {
              if (value)
                onChange({ ...value, subjectId: event.target.value || null });
            }}
          >
            <option value="">{t("transactionFacts")}</option>
            {selected?.parcelSubjectIds.map((subject) => (
              <option value={subject} key={subject}>
                {t("parcelNumber", {
                  number:
                    subjects.find((row) => row.id === subject)?.ordinal ?? 0,
                })}{" "}
                &middot; {subject}
              </option>
            ))}
            {[
              ...new Set(
                selected?.partyRoles.map((role) => role.subjectId) ?? [],
              ),
            ].map((subject) => (
              <option value={subject} key={subject}>
                {t("party")}{" "}
                {subjects.find((row) => row.id === subject)?.ordinal} &middot;{" "}
                {subject}
              </option>
            ))}
          </select>
        </label>
      </div>
      {value && (
        <p className="text-muted-ink text-xs">
          {t("version", { version: value.associationVersion })}
        </p>
      )}
      <Button
        variant="secondary"
        disabled={disabled || loading}
        onClick={() => {
          onChange(null);
          void load();
        }}
      >
        {t("renew")}
      </Button>
    </section>
  );
}
