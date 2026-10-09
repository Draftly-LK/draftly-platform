"use client";
import { useCallback, useEffect, useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { listTransactions, listSubjects } from "@/lib/api/facts";
import type { TokenProvider } from "@/lib/api/client";
import type { RunChecksBody } from "@/lib/api/checks";
import type { ApiMatterTransaction, ApiMatterSubject } from "@/types/rta";
export function CheckScopeSelector({
  matterId,
  getToken,
  value,
  onChange,
}: {
  matterId: string;
  getToken: TokenProvider;
  value: RunChecksBody | null;
  onChange: (scope: RunChecksBody | null) => void;
}) {
  const t = useTranslations("checkScope");
  const id = useId();
  const [transactions, setTransactions] = useState<ApiMatterTransaction[]>([]);
  const [subjects, setSubjects] = useState<ApiMatterSubject[]>([]);
  const [error, setError] = useState(false);
  const load = useCallback(async () => {
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
      setTransactions(all);
      setSubjects(allSubjects);
      setError(false);
    } catch {
      setError(true);
      onChange(null);
    }
  }, [getToken, matterId, onChange]);
  useEffect(() => {
    void load();
  }, [load]);
  const selected = transactions.find((row) => row.id === value?.transactionId);
  const stale = value && selected?.version !== value.associationVersion;
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
            disabled={error}
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
            disabled={error || !selected || !!stale}
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
