"use client";

import { useCallback, useEffect, useId, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Button, buttonClass } from "@/components/ui/button";
import { listSubjects, listTransactions } from "@/lib/api/facts";
import type { TokenProvider } from "@/lib/api/client";
import type {
  ApiFormScope,
  ApiMatterSubject,
  ApiMatterTransaction,
} from "@/types/rta";

export function FormScopeSelector({
  matterId,
  getToken,
  value,
  onChange,
}: {
  matterId: string;
  getToken: TokenProvider;
  value: ApiFormScope | null;
  onChange: (scope: ApiFormScope | null) => void;
}) {
  const t = useTranslations("formScope");
  const id = useId();
  const [transactions, setTransactions] = useState<ApiMatterTransaction[]>([]);
  const [subjects, setSubjects] = useState<ApiMatterSubject[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const allTransactions: ApiMatterTransaction[] = [];
      const allSubjects: ApiMatterSubject[] = [];
      for (const kind of ["transactions", "subjects"] as const) {
        let cursor: string | undefined;
        const seen = new Set<string>();
        do {
          const params = { limit: 100, cursor };
          const page =
            kind === "transactions"
              ? await listTransactions(getToken, matterId, params)
              : await listSubjects(getToken, matterId, params);
          if (kind === "transactions")
            allTransactions.push(...(page.items as ApiMatterTransaction[]));
          else allSubjects.push(...(page.items as ApiMatterSubject[]));
          if (page.page.hasMore && !page.page.nextCursor)
            throw new Error("Incomplete scope page");
          cursor = page.page.hasMore
            ? (page.page.nextCursor ?? undefined)
            : undefined;
          if (cursor && seen.has(cursor))
            throw new Error("Repeated scope page");
          if (cursor) seen.add(cursor);
        } while (cursor && seen.size < 100);
        if (cursor) throw new Error("Incomplete scope");
      }
      if (
        allTransactions.some((row) =>
          [
            ...row.parcelSubjectIds,
            ...row.partyRoles.map((role) => role.subjectId),
          ].some((subject) => !allSubjects.some((item) => item.id === subject)),
        )
      )
        throw new Error("Missing subject");
      setTransactions(allTransactions);
      setSubjects(allSubjects);
      setError(false);
    } catch {
      setError(true);
      onChange(null);
    } finally {
      setLoading(false);
    }
  }, [getToken, matterId, onChange]);
  useEffect(() => {
    void load();
  }, [load]);
  const selected = transactions.find((row) => row.id === value?.transactionId);
  const empty = !loading && !error && transactions.length === 0;
  const incomplete = Boolean(
    selected &&
      (!selected.parcelSubjectIds.length ||
        !selected.partyRoles.some((row) => row.role === "transferor") ||
        !selected.partyRoles.some((row) => row.role === "transferee")),
  );
  const control =
    "border-border-control bg-surface rounded-control min-h-10 w-full border px-3 py-2 text-sm";
  return (
    <section
      className="border-border mb-6 space-y-3 border-b pb-5"
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
      {error && !loading && (
        <p role="alert" className="text-red">
          {t("unavailable")}
        </p>
      )}
      {empty && (
        <p role="status" className="text-muted-ink text-sm">
          {t("empty")}
        </p>
      )}
      {!loading && !error && !empty && (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm" htmlFor={`${id}-transaction`}>
            {t("transaction")}
            <select
              id={`${id}-transaction`}
              className={control}
              disabled={loading || error}
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
                        parcelSubjectId: null,
                        transferorSubjectId: null,
                        transfereeSubjectId: null,
                      }
                    : null,
                );
              }}
            >
              <option value="">{t("choose")}</option>
              {transactions.map((row) => (
                <option key={row.id} value={row.id}>
                  {t("transactionNumber", { number: row.ordinal })}
                </option>
              ))}
            </select>
          </label>
          {(["parcel", "transferor", "transferee"] as const).map((role) => {
            const key = `${role}SubjectId` as const;
            const choices =
              role === "parcel"
                ? (selected?.parcelSubjectIds ?? [])
                : (selected?.partyRoles
                    .filter((item) => item.role === role)
                    .map((item) => item.subjectId) ?? []);
            return (
              <label
                key={role}
                className="space-y-1 text-sm"
                htmlFor={`${id}-${role}`}
              >
                {t(role)}
                <select
                  id={`${id}-${role}`}
                  className={control}
                  disabled={loading || error || !selected}
                  value={value?.[key] ?? ""}
                  onChange={(event) => {
                    if (value)
                      onChange({ ...value, [key]: event.target.value || null });
                  }}
                >
                  <option value="">{t("unassigned")}</option>
                  {[...new Set(choices)].map((subject) => (
                    <option key={subject} value={subject}>
                      {t(role === "parcel" ? "parcelNumber" : "partyNumber", {
                        number:
                          subjects.find((row) => row.id === subject)?.ordinal ??
                          0,
                      })}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
      )}
      {!loading && !error && incomplete && (
        <p className="text-muted-ink text-sm">{t("incomplete")}</p>
      )}
      {(empty || (!loading && !error && incomplete)) && (
        <Link
          className={buttonClass("primary")}
          href={`/matters/${matterId}/facts#transaction-scope`}
        >
          {t("setup")}
        </Link>
      )}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Button
          variant="secondary"
          disabled={loading}
          onClick={() => {
            onChange(null);
            void load();
          }}
        >
          {t("renew")}
        </Button>
        <Link className="underline" href={`/matters/${matterId}/facts`}>
          {t("openRegister")}
        </Link>
      </div>
    </section>
  );
}
