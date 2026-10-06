"use client";

import {
  BookOpen,
  ExternalLink,
  FilePenLine,
  WifiOff,
  Search,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
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
        <nav
          className="border-border mb-6 flex flex-wrap gap-2 border-b pb-3"
          aria-label={t("title")}
        >
          {(["statutes", "cases"] as const).map((value) => (
            <Button
              key={value}
              aria-pressed={tab === value}
              className={
                tab === value
                  ? "border-forest bg-selected-bg text-forest"
                  : undefined
              }
              onClick={() => {
                setTab(value);
                window.history.replaceState(
                  null,
                  "",
                  value === "cases" ? "/library?tab=cases" : "/library",
                );
              }}
            >
              {cases(value === "cases" ? "tab" : "statutesTab")}
            </Button>
          ))}
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
  const amendmentCount = sources.length - statuteCount;

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
          <div className="border-border bg-surface divide-border rounded-card grid divide-y border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            <Count label={t("all")} value={loading ? null : sources.length} />
            <Count
              label={t("statutes")}
              value={loading ? null : statuteCount}
            />
            <Count
              label={t("amendments")}
              value={loading ? null : amendmentCount}
            />
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
                          aria-hidden="true"
                          className="text-forest size-5"
                          strokeWidth={1.5}
                        />
                        <div className="min-w-0">
                          <h2 className="font-heading text-lg font-semibold">
                            {source.title}
                          </h2>
                          <p className="text-muted-ink flex flex-wrap gap-x-3 text-sm">
                            <span>
                              {source.type === "amendment"
                                ? t("amendment")
                                : t("statute")}
                            </span>
                            <span className="tabular-nums">
                              {source.reference}
                            </span>
                          </p>
                          <p className="text-muted-ink mt-1 text-xs">
                            {t("sectionCount", { count: source.sectionCount })}
                          </p>
                        </div>
                        <a
                          className="text-forest focus-visible:outline-ring inline-flex items-center gap-1 text-sm font-semibold hover:underline"
                          href={source.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t("open")}
                          <ExternalLink
                            aria-hidden="true"
                            className="size-4"
                            strokeWidth={1.5}
                          />
                        </a>
                      </article>
                    );
                  })}
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

/** One figure, centred in its third of the summary card. */
function Count({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="px-4 py-5 text-center">
      <div className="font-heading text-3xl font-semibold tabular-nums">
        {value ?? "—"}
      </div>
      <div className="text-muted-ink text-sm">{label}</div>
    </div>
  );
}
