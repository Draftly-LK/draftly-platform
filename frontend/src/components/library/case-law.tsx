"use client";

import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  ExternalLink,
  Info,
  LoaderCircle,
  Search,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { ApiError, type TokenProvider } from "@/lib/api/client";
import {
  getCase,
  listCases,
  searchCases,
  type CaseFilters,
} from "@/lib/api/library";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type {
  CaseCoverage,
  CaseDetail,
  CasePage,
  CaseRecord,
  CaseSearch,
  SimilarCase,
} from "@/types/case";
import {
  caseCollectionLabels,
  caseQualityLabels,
  caseSignalLabels,
} from "@/lib/i18n/case-labels";
import { buttonClass } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const control =
  "border-border-control bg-surface min-h-10 min-w-0 rounded-control border px-3 py-2";
const button = buttonClass("secondary");
const icon = "size-4 shrink-0";

function Notice({
  children,
  alert = false,
}: {
  children: React.ReactNode;
  alert?: boolean;
}) {
  return (
    <div
      role={alert ? "alert" : undefined}
      className={`rounded-card flex items-start gap-2 border p-3 text-sm ${alert ? "border-red bg-red-bg text-red" : "border-border bg-canvas text-muted-ink"}`}
    >
      {alert ? (
        <AlertTriangle aria-hidden="true" className={icon} strokeWidth={1.5} />
      ) : (
        <Info aria-hidden="true" className={icon} strokeWidth={1.5} />
      )}
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Loading({ search = false }: { search?: boolean }) {
  const t = useTranslations("caseLaw");
  return (
    <p role="status" className="text-muted-ink flex items-center gap-2 py-6">
      <LoaderCircle
        aria-hidden="true"
        className="size-5 animate-spin"
        strokeWidth={1.5}
      />
      {t(search ? "searching" : "loading")}
    </p>
  );
}

function Coverage({
  coverage,
  version,
}: {
  coverage: CaseCoverage;
  version: string;
}) {
  const t = useTranslations("caseLaw");
  return (
    <div className="border-border bg-surface rounded-card space-y-1 border p-4 text-sm">
      <p className="font-semibold tabular-nums">
        {coverage.minYear !== null && coverage.maxYear !== null
          ? t("coverage", {
              count: coverage.catalogueRecords,
              minYear: String(coverage.minYear),
              maxYear: String(coverage.maxYear),
            })
          : t("coverageUnknown", { count: coverage.catalogueRecords })}
      </p>
      <p className="text-muted-ink">
        {t("searchCoverage", {
          count: coverage.retrievalRecords,
          overlap: coverage.readerOverlapRecords,
        })}
      </p>
      <p className="text-muted-ink break-words text-xs">
        {t("version", { version })}
      </p>
    </div>
  );
}

function SourceLink({ url }: { url: string }) {
  const t = useTranslations("caseLaw");
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="text-teal inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
    >
      {t("source")}
      <ExternalLink aria-hidden="true" className={icon} strokeWidth={1.5} />
    </a>
  );
}

function CaseMetadata({ item }: { item: CaseRecord }) {
  const t = useTranslations("caseLaw");
  const locale = useLocale() === "si" ? "si" : "en";
  return (
    <div className="space-y-2">
      <p className="text-muted-ink break-words text-sm">
        {item.citation} · {item.year} ·{" "}
        {caseCollectionLabels[item.collection][locale]}
      </p>
      <p className="text-muted-ink text-sm">
        {t("decidingCourt")}: {item.decidingCourt ?? t("courtUnknown")}
      </p>
    </div>
  );
}

type BrowseRequest = {
  filters: CaseFilters;
  cursor?: string;
  previous: (string | undefined)[];
};

/** Real authenticated catalogue/search flow, also mounted by the test-only review harness. */
export function CaseCatalogueFlow({ getToken }: { getToken: TokenProvider }) {
  const t = useTranslations("caseLaw");
  const locale = useLocale() === "si" ? "si" : "en";
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState<"" | "LKCA" | "LKSC">("");
  const [year, setYear] = useState("");
  const [request, setRequest] = useState<BrowseRequest>({
    filters: {},
    previous: [],
  });
  const [page, setPage] = useState<CasePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"unavailable" | "cursor" | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void listCases(getToken, {
      ...request.filters,
      limit: 25,
      cursor: request.cursor,
    })
      .then((result) => {
        if (active) setPage(result);
      })
      .catch((cause: unknown) => {
        if (active)
          setError(
            cause instanceof ApiError && cause.code === "invalid_cursor"
              ? "cursor"
              : "unavailable",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [getToken, request, retry]);

  return (
    <section data-case-flow className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{t("catalogue")}</h2>
        <p className="text-muted-ink mt-1">{t("catalogueDescription")}</p>
        <a
          className="text-teal mt-2 inline-flex items-center gap-2 font-medium hover:underline"
          href="#case-search"
          onClick={() => document.getElementById("case-search")?.focus()}
        >
          <Search aria-hidden="true" className={icon} strokeWidth={1.5} />
          {t("jumpToSearch")}
        </a>
      </div>
      {page && (
        <Coverage coverage={page.coverage} version={page.corpusVersion} />
      )}
      <form
        className="grid items-end gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_7rem_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          setRequest({
            filters: {
              query: query.trim() || undefined,
              collection: collection || undefined,
              year: year ? Number(year) : undefined,
            },
            previous: [],
          });
        }}
      >
        <label className="grid min-w-0 gap-1 text-sm font-medium">
          {t("name")}
          <input
            className={control}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1 text-sm font-medium">
          {t("collection")}
          <select
            className={control}
            value={collection}
            onChange={(event) =>
              setCollection(event.target.value as typeof collection)
            }
          >
            <option value="">{t("allCollections")}</option>
            <option value="LKCA">{caseCollectionLabels.LKCA[locale]}</option>
            <option value="LKSC">{caseCollectionLabels.LKSC[locale]}</option>
          </select>
        </label>
        <label className="grid min-w-0 gap-1 text-sm font-medium">
          {t("year")}
          <input
            type="number"
            min={1700}
            max={2200}
            className={control}
            value={year}
            onChange={(event) => setYear(event.target.value)}
          />
        </label>
        <button className={button} type="submit">
          <Search aria-hidden="true" className={icon} strokeWidth={1.5} />
          {t("apply")}
        </button>
      </form>
      <p className="text-muted-ink text-xs">{t("collectionNotice")}</p>
      {loading && <Loading />}
      {!loading && error && (
        <Notice alert>
          <p>
            {t(error === "cursor" ? "staleCursor" : "catalogueUnavailable")}
          </p>
          <button
            className={`${button} mt-3`}
            onClick={() =>
              error === "cursor"
                ? setRequest({ filters: request.filters, previous: [] })
                : setRetry((value) => value + 1)
            }
          >
            {t(error === "cursor" ? "restart" : "retry")}
          </button>
        </Notice>
      )}
      {!loading && !error && page && (
        <div aria-live="polite" className="space-y-4">
          {page.items.length ? (
            <div className="divide-border border-border bg-surface rounded-card divide-y border">
              {page.items.map((item) => (
                <article key={item.id} className="space-y-2 p-4">
                  <h3 className="break-words text-lg font-semibold">
                    <a
                      className="text-forest hover:underline"
                      href={`/library/cases/${encodeURIComponent(item.id)}`}
                    >
                      {item.title}
                    </a>
                  </h3>
                  <CaseMetadata item={item} />
                  <SourceLink url={item.sourceUrl} />
                </article>
              ))}
            </div>
          ) : (
            <Notice>{t("emptyCatalogue")}</Notice>
          )}
          <nav
            aria-label={t("catalogue")}
            className="flex flex-wrap justify-between gap-3"
          >
            <button
              className={button}
              disabled={!request.previous.length}
              onClick={() =>
                setRequest({
                  filters: request.filters,
                  cursor: request.previous.at(-1),
                  previous: request.previous.slice(0, -1),
                })
              }
            >
              <ArrowLeft
                aria-hidden="true"
                className={icon}
                strokeWidth={1.5}
              />
              {t("previous")}
            </button>
            <button
              className={button}
              disabled={!page.page.hasMore || !page.page.nextCursor}
              onClick={() =>
                setRequest({
                  filters: request.filters,
                  cursor: page.page.nextCursor ?? undefined,
                  previous: [...request.previous, request.cursor],
                })
              }
            >
              {t("next")}
              <ArrowRight
                aria-hidden="true"
                className={icon}
                strokeWidth={1.5}
              />
            </button>
          </nav>
        </div>
      )}
      <CaseSearchFlow getToken={getToken} />
    </section>
  );
}

function SimilarResult({ item }: { item: SimilarCase }) {
  const t = useTranslations("caseLaw");
  const locale = useLocale() === "si" ? "si" : "en";
  const reader = item.readerAvailable && item.case !== null;
  return (
    <article className="space-y-2 p-4">
      <h3 className="break-words text-lg font-semibold">
        <a
          className="text-forest hover:underline"
          href={
            reader
              ? `/library/cases/${encodeURIComponent(item.id)}`
              : item.sourceUrl
          }
          {...(!reader ? { target: "_blank", rel: "noreferrer" } : {})}
        >
          {item.title}
          {!reader && (
            <ExternalLink
              aria-hidden="true"
              className="ml-1 inline size-4"
              strokeWidth={1.5}
            />
          )}
        </a>
      </h3>
      {item.case ? (
        <CaseMetadata item={item.case} />
      ) : (
        <>
          <p className="text-muted-ink text-sm">{item.citation}</p>
          <p className="text-muted-ink text-xs">{t("outsideCatalogue")}</p>
        </>
      )}
      <div className="flex flex-wrap gap-2">
        {item.matchedSignals.map((signal) => (
          <span
            key={signal}
            className="border-border text-muted-ink rounded-control inline-flex items-center gap-1 border px-2 py-1 text-xs"
          >
            <Search aria-hidden="true" className="size-3" strokeWidth={1.5} />
            {caseSignalLabels[signal][locale]}
          </span>
        ))}
      </div>
      <p className="text-muted-ink text-xs font-medium">{t("excerpt")}</p>
      <p className="whitespace-pre-wrap break-words text-sm">
        {item.excerpt.slice(0, 900)}
      </p>
      <SourceLink url={item.sourceUrl} />
    </article>
  );
}

export function CaseSearchFlow({ getToken }: { getToken: TokenProvider }) {
  const t = useTranslations("caseLaw");
  const [facts, setFacts] = useState("");
  const [result, setResult] = useState<CaseSearch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<"unavailable" | "denied" | null>(null);
  const attempt = useRef<{ query: string; key: string } | null>(null);
  const inFlight = useRef(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);

  async function search(retry = false) {
    const query = retry ? attempt.current?.query : facts.trim();
    if (!query || inFlight.current) return;
    if (attempt.current?.query !== query)
      attempt.current = { query, key: crypto.randomUUID() };
    const key = attempt.current!.key;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await searchCases(getToken, query, key);
      if (active.current) setResult(response);
    } catch (cause: unknown) {
      if (active.current)
        setError(
          cause instanceof ApiError &&
            (cause.status === 403 || cause.status === 429)
            ? "denied"
            : "unavailable",
        );
    } finally {
      inFlight.current = false;
      if (active.current) setLoading(false);
    }
  }

  return (
    <section
      id="case-search"
      tabIndex={-1}
      className="border-border space-y-4 border-t pt-6"
      aria-labelledby="case-search-title"
    >
      <div>
        <h2 id="case-search-title" className="text-xl font-semibold">
          {t("searchTitle")}
        </h2>
        <p className="text-muted-ink mt-1">{t("searchDescription")}</p>
      </div>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <label className="grid gap-1 text-sm font-medium">
          {t("facts")}
          <textarea
            className={cn(control, "min-h-28 w-full resize-y rounded")}
            maxLength={8000}
            required
            disabled={loading}
            value={facts}
            onChange={(event) => {
              setFacts(event.target.value);
              setResult(null);
              setError(null);
            }}
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            className={buttonClass("primary")}
            disabled={loading || !facts.trim()}
          >
            <Search aria-hidden="true" className={icon} strokeWidth={1.5} />
            {t("submitSearch")}
          </button>
          <p className="text-muted-ink text-xs">{t("searchScope")}</p>
        </div>
      </form>
      {loading && <Loading search />}
      {error && (
        <Notice alert>
          <p>{t(error === "denied" ? "searchDenied" : "searchUnavailable")}</p>
          {error === "unavailable" && (
            <button
              className={`${button} mt-3`}
              onClick={() => {
                void search(true);
              }}
            >
              {t("retrySearch")}
            </button>
          )}
        </Notice>
      )}
      {result && (
        <div className="space-y-3" aria-live="polite">
          <Notice>
            {t(
              result.denseStatus === "disabled"
                ? "denseDisabled"
                : result.denseStatus === "unavailable"
                  ? "denseUnavailable"
                  : "denseUnknown",
            )}
            {result.degradedChannels.includes("dense") &&
              result.denseStatus === "enabled-status-unknown" && (
                <p className="mt-1">{t("denseDegraded")}</p>
              )}
          </Notice>
          <p className="text-muted-ink text-xs">
            {t("searchCoverage", {
              count: result.coverage.retrievalRecords,
              overlap: result.coverage.readerOverlapRecords,
            })}
          </p>
          {result.outcome === "no_similar_cases" || !result.items.length ? (
            <Notice>{t("searchNoResults")}</Notice>
          ) : (
            <>
              <p className="font-medium">
                {t("resultCount", { count: Math.min(result.items.length, 8) })}
              </p>
              <div className="divide-border border-border bg-surface rounded-card divide-y border">
                {result.items.slice(0, 8).map((item) => (
                  <SimilarResult key={item.id} item={item} />
                ))}
              </div>
            </>
          )}
        </div>
      )}
      <Notice>{t("limitations")}</Notice>
    </section>
  );
}

export function CaseReaderScreen({ caseId }: { caseId: string }) {
  const t = useTranslations("caseLaw");
  const getToken = useTokenProvider();
  return (
    <AppShell>
      <PageHeader title={t("readerTitle")} />
      <div className="p-6">
        <CaseReaderFlow getToken={getToken} caseId={caseId} />
      </div>
    </AppShell>
  );
}

export function CaseReaderFlow({
  getToken,
  caseId,
}: {
  getToken: TokenProvider;
  caseId: string;
}) {
  const t = useTranslations("caseLaw");
  const locale = useLocale() === "si" ? "si" : "en";
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"missing" | "unavailable" | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setDetail(null);
    void getCase(getToken, caseId)
      .then((response) => {
        if (active) setDetail(response);
      })
      .catch((cause: unknown) => {
        if (active)
          setError(
            cause instanceof ApiError && cause.status === 404
              ? "missing"
              : "unavailable",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [getToken, caseId, retry]);
  const item = detail?.item;
  const display =
    item?.displayPolicy === "full-text" &&
    item.text !== null &&
    Boolean(item.displayApprovalReference?.trim());
  return (
    <section data-case-flow className="mx-auto max-w-4xl space-y-5">
      <a
        className="text-teal inline-flex items-center gap-2 font-medium hover:underline"
        href="/library?tab=cases"
      >
        <ArrowLeft aria-hidden="true" className={icon} strokeWidth={1.5} />
        {t("back")}
      </a>
      {loading && <Loading />}
      {error && (
        <Notice alert>
          <p>{t(error === "missing" ? "notFound" : "readerUnavailable")}</p>
          {error !== "missing" && (
            <button
              className={`${button} mt-3`}
              onClick={() => setRetry((value) => value + 1)}
            >
              {t("retry")}
            </button>
          )}
        </Notice>
      )}
      {item && detail && (
        <>
          <article className="border-border bg-surface rounded-card space-y-4 border p-5">
            <h2 className="break-words text-2xl font-semibold">{item.title}</h2>
            <CaseMetadata item={item} />
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-ink">{t("decisionDate")}</dt>
                <dd>{item.decisionDate ?? t("unavailableValue")}</dd>
              </div>
              <div>
                <dt className="text-muted-ink">{t("reportSeries")}</dt>
                <dd>{item.reportSeries ?? t("unavailableValue")}</dd>
              </div>
            </dl>
            <p className="text-muted-ink text-sm">{t("provenance")}</p>
            <SourceLink url={item.sourceUrl} />
            {item.qualityWarnings.length > 0 && (
              <ul className="space-y-2">
                {item.qualityWarnings.map((warning) => (
                  <li
                    key={warning}
                    className="text-amber-text flex items-start gap-2 text-sm"
                  >
                    <AlertTriangle
                      aria-hidden="true"
                      className={icon}
                      strokeWidth={1.5}
                    />
                    {caseQualityLabels[warning][locale]}
                  </li>
                ))}
              </ul>
            )}
          </article>
          {display ? (
            <article className="border-border bg-surface rounded-card space-y-3 border p-5">
              <h3 className="flex items-center gap-2 text-lg font-semibold">
                <BookOpen
                  aria-hidden="true"
                  className="size-5"
                  strokeWidth={1.5}
                />
                {t("fullText")}
              </h3>
              <p className="text-muted-ink break-words text-xs">
                {t("approval", { reference: item.displayApprovalReference! })}
              </p>
              <div
                data-case-text
                className="whitespace-pre-wrap break-words leading-relaxed"
              >
                {item.text}
              </div>
            </article>
          ) : (
            <Notice>{t("metadataOnly")}</Notice>
          )}
          <Notice>{t("limitations")}</Notice>
          <Coverage coverage={detail.coverage} version={detail.corpusVersion} />
        </>
      )}
    </section>
  );
}
