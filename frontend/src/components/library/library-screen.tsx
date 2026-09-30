"use client";

import {
  BookOpen,
  ExternalLink,
  FilePenLine,
  LoaderCircle,
  Search,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { listLegalSources } from "@/lib/api/library";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { LegalSourceSummary, LegalSourceType } from "@/types";

type SourceFilter = "all" | LegalSourceType;

/**
 * `useTokenProvider` calls Clerk's `useAuth`, which requires a `ClerkProvider`.
 * The offline demo runs without one, so the hook lives in a component that is
 * only mounted when the backend is configured. Offline, no request is made, so
 * the token provider is never called.
 */
export function LibraryScreen() {
  return isApiEnabled() ? <ApiBoundLibraryScreen /> : <LibraryFlow getToken={offlineToken} />;
}

const offlineToken: TokenProvider = () => Promise.resolve(null);

function ApiBoundLibraryScreen() {
  const getToken = useTokenProvider();
  return <LibraryFlow getToken={getToken} />;
}

function LibraryFlow({ getToken }: { getToken: TokenProvider }) {
  const t = useTranslations("library");
  const [sources, setSources] = useState<LegalSourceSummary[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<SourceFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!isApiEnabled()) {
      setError(true);
      setLoading(false);
      return;
    }
    let active = true;
    void listLegalSources(getToken)
      .then(({ items }) => {
        if (active) setSources(items);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [getToken]);

  const visibleSources = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return sources.filter((source) => {
      const matchesType = filter === "all" || source.type === filter;
      const matchesQuery =
        !normalized ||
        source.title.toLocaleLowerCase().includes(normalized) ||
        source.reference.toLocaleLowerCase().includes(normalized) ||
        source.id.toLocaleLowerCase().includes(normalized);
      return matchesType && matchesQuery;
    });
  }, [filter, query, sources]);

  const statuteCount = sources.filter(
    (source) => source.type === "statute",
  ).length;
  const amendmentCount = sources.length - statuteCount;

  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <main className="p-4 md:p-6">
        <div className="border-border bg-surface grid gap-4 rounded-card border p-4 sm:grid-cols-3 shadow-card">
          <Count label={t("all")} value={sources.length} />
          <Count label={t("statutes")} value={statuteCount} />
          <Count label={t("amendments")} value={amendmentCount} />
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <label className="border-border-strong bg-surface flex h-10 min-w-64 flex-1 items-center gap-2 rounded border px-3">
            <Search className="text-muted-ink size-4" strokeWidth={1.5} />
            <span className="sr-only">{t("search")}</span>
            <input
              className="min-w-0 flex-1 bg-transparent outline-none"
              placeholder={t("search")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <select
            aria-label={t("filterLabel")}
            className="border-border-strong bg-surface h-10 rounded border px-3"
            value={filter}
            onChange={(event) =>
              setFilter(event.target.value as SourceFilter)
            }
          >
            <option value="all">{t("all")}</option>
            <option value="statute">{t("statutes")}</option>
            <option value="amendment">{t("amendments")}</option>
          </select>
        </div>

        {loading && (
          <div className="text-muted-ink flex items-center justify-center gap-2 py-20">
            <LoaderCircle className="size-5 animate-spin" />
            {t("loading")}
          </div>
        )}
        {error && !loading && (
          <div
            role="alert"
            className="border-red bg-red-bg mt-5 border-l-2 p-4"
          >
            {t("loadFailed")}
          </div>
        )}
        {!loading && !error && (
          <>
            <p className="text-muted-ink mt-4 text-sm">
              {t("resultCount", { count: visibleSources.length })}
            </p>
            <div className="divide-border border-border bg-surface mt-3 divide-y border-y">
              {visibleSources.map((source) => {
                const Icon =
                  source.type === "amendment" ? FilePenLine : BookOpen;
                return (
                  <article
                    key={source.id}
                    className="grid min-h-20 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 px-4 py-3"
                  >
                    <Icon
                      className="text-forest size-5"
                      strokeWidth={1.5}
                    />
                    <div className="min-w-0">
                      <h2 className="font-heading text-lg font-semibold">
                        {source.title}
                      </h2>
                      <p className="text-muted-ink text-sm">
                        {source.type === "amendment"
                          ? t("amendment")
                          : t("statute")}{" "}
                        · {source.reference}
                      </p>
                      <p className="text-muted-ink mt-1 text-xs">
                        {t("sectionCount", { count: source.sectionCount })}
                      </p>
                    </div>
                    <a
                      className="text-teal focus-visible:outline-ring inline-flex items-center gap-1 text-sm font-semibold hover:underline"
                      href={source.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {t("open")}
                      <ExternalLink className="size-4" strokeWidth={1.5} />
                    </a>
                  </article>
                );
              })}
            </div>
            {visibleSources.length === 0 && (
              <div className="text-muted-ink py-16 text-center">
                {t("noResults")}
              </div>
            )}
          </>
        )}
        <div className="border-amber bg-amber-bg text-amber-text mt-6 border-l-2 p-4">
          {t("corpusNotice")}
        </div>
      </main>
    </AppShell>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="font-heading text-3xl font-semibold tabular-nums">
        {value}
      </div>
      <div className="text-muted-ink text-sm">{label}</div>
    </div>
  );
}
