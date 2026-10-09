"use client";

import { ExternalLink, WifiOff, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { RowsSkeleton } from "@/components/ui/skeleton";
import { isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { listLegalSources } from "@/lib/api/library";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { LegalSourceSummary, LegalSourceType } from "@/types";
import { CaseCatalogueFlow } from "./case-law";
export { CaseReaderFlow } from "./case-law";

type SourceFilter = "all" | LegalSourceType;

/**
 * `useTokenProvider` calls Clerk's `useAuth`, which requires a `ClerkProvider`.
 * The offline demo runs without one, so the hook lives in a component that is
 * only mounted when the backend is configured. Offline, no request is made, so
 * the token provider is never called.
 */
export function LibraryScreen() {
  return isApiEnabled() ? (
    <ApiBoundLibraryScreen />
  ) : (
    <LibraryFlow getToken={offlineToken} />
  );
}

const offlineToken: TokenProvider = () => Promise.resolve(null);

function ApiBoundLibraryScreen() {
  const getToken = useTokenProvider();
  return <LibraryFlow getToken={getToken} />;
}

export function LibraryFlow({ getToken }: { getToken: TokenProvider }) {
  const cases = useTranslations("caseLaw");
  const [tab, setTab] = useState<"statutes" | "cases">("statutes");
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tab") === "cases")
      setTab("cases");
  }, []);
  const t = useTranslations("library");
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <nav className="border-border mb-6 border-b pb-3" aria-label={t("title")}>
          <SegmentedControl
            label={t("title")}
            options={[
              { value: "statutes", label: cases("statutesTab") },
              { value: "cases", label: cases("tab") },
            ]}
            value={tab}
            onChange={(value) => {
              setTab(value);
              window.history.replaceState(
                null,
                "",
                value === "cases" ? "/library?tab=cases" : "/library",
              );
            }}
          />
        </nav>
        {tab === "cases" ? (
          <CaseCatalogueFlow getToken={getToken} />
        ) : (
          <StatutorySources getToken={getToken} />
        )}
      </div>
    </AppShell>
  );
}

function StatutorySources({ getToken }: { getToken: TokenProvider }) {
  const t = useTranslations("library");
  const [sources, setSources] = useState<LegalSourceSummary[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<SourceFilter>("all");
  // Offline (no backend) is not a failure: the corpus simply is not here, and
  // the page says so instead of showing an error.
  const offline = !isApiEnabled();
  const [loading, setLoading] = useState(!offline);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (offline) return;
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
  }, [getToken, offline]);

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
  const amendmentCount = sources.filter((source) => source.type === "amendment").length;
  const gazetteCount = sources.filter((source) => source.type === "gazette").length;

  return (
    <section>
      {offline ? (
        <EmptyState
          icon={WifiOff}
          title={t("offlineTitle")}
          description={t("offlineBody")}
        />
      ) : error && !loading ? (
        <ErrorState
          title={t("loadFailed")}
          action={
            <Button onClick={() => window.location.reload()}>
              {t("retry")}
            </Button>
          }
        >
          {t("loadFailedHelp")}
        </ErrorState>
      ) : (
        <>
          <div className="border-border bg-surface divide-border rounded-card grid grid-cols-4 divide-x border">
            <Count label={t("all")} value={loading ? null : sources.length} />
            <Count
              label={t("statutes")}
              value={loading ? null : statuteCount}
            />
            <Count
              label={t("amendments")}
              value={loading ? null : amendmentCount}
            />
            <Count label={t("gazettes")} value={loading ? null : gazetteCount} />
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <label className="border-border-control bg-surface rounded-control flex h-10 min-w-64 flex-1 items-center gap-2 border px-3 focus-within:border-forest focus-within:ring-4 focus-within:ring-border-active">
              <Search className="text-muted-ink size-4" strokeWidth={1.5} />
              <span className="sr-only">{t("search")}</span>
              <input
                className="min-w-0 flex-1 bg-transparent outline-none focus-visible:outline-none"
                placeholder={t("search")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <select
              aria-label={t("filterLabel")}
              className="border-border-control bg-surface rounded-control h-10 border px-3"
              value={filter}
              onChange={(event) =>
                setFilter(event.target.value as SourceFilter)
              }
            >
              <option value="all">{t("all")}</option>
              <option value="statute">{t("statutes")}</option>
              <option value="amendment">{t("amendments")}</option>
              <option value="gazette">{t("gazettes")}</option>
            </select>
          </div>

          {loading ? (
            <RowsSkeleton
              label={t("loading")}
              rows={4}
              className="border-border bg-surface rounded-card mt-4 border"
            />
          ) : (
            <>
              <p className="text-muted-ink mt-4 text-sm">
                {t("resultCount", { count: visibleSources.length })}
              </p>
              {visibleSources.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title={t("noResults")}
                  description={t("noResultsHelp")}
                  action={
                    <Button
                      onClick={() => {
                        setQuery("");
                        setFilter("all");
                      }}
                    >
                      {t("clearFilters")}
                    </Button>
                  }
                />
              ) : (
                <div className="divide-border border-border bg-surface rounded-card mt-3 divide-y border">
                  {visibleSources.map((source) => (
                    <article key={source.id} className="space-y-2 p-4">
                      <h2 className="break-words text-lg font-semibold">
                        <a
                          className="text-forest hover:underline"
                          href={source.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {source.title}
                        </a>
                      </h2>
                      <p className="text-muted-ink break-words text-sm">
                        {source.type === "gazette" ? t("gazettes") : source.type === "amendment" ? t("amendment") : t("statute")}
                        {" · "}
                        <span className="tabular-nums">{source.reference}</span>
                        {" · "}
                        {t("sectionCount", { count: source.sectionCount })}
                      </p>
                      <a
                        className="text-teal inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
                        href={source.sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t("open")}
                        <ExternalLink aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
                      </a>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
      <div className="border-amber bg-amber-bg text-amber-text mt-6 border-l-2 p-4">
        {t("corpusNotice")}
      </div>
    </section>
  );
}

/** One figure, centred in its third of the summary card; smaller on phones so all three share a row. */
function Count({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="min-w-0 px-2 py-3 text-center sm:px-4 sm:py-5">
      <div className="font-heading text-xl font-semibold tabular-nums sm:text-3xl">
        {value ?? "—"}
      </div>
      <div className="text-muted-ink truncate text-xs sm:text-sm">{label}</div>
    </div>
  );
}
