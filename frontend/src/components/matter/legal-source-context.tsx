"use client";
import { useCallback, useEffect, useId, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { listTransactions } from "@/lib/api/facts";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiMatterTransaction } from "@/types/rta";
import type {
  ApiAgentCitation,
  ApiLegalAuthority,
  ApiLegalContext,
  ApiResearchSelection,
} from "@/lib/api/agent";

export type LegalSourceSelection = ApiAgentCitation & {
  legalContext?: ApiLegalContext | null;
  metadataLead?: boolean;
};
function lead(
  authority: ApiLegalAuthority,
  context?: ApiLegalContext | null,
): LegalSourceSelection {
  return {
    sourceId: authority.sourceId,
    sourceType: authority.kind,
    label: authority.reference || authority.title,
    locator: null,
    verificationStatus: "unverified",
    authorityMetadata: authority,
    corpusVersion: authority.releaseVersion,
    legalContext: context,
    metadataLead: true,
  };
}
function officialUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
export function LegalTransactionSelector({
  matterId,
  value,
  onChange,
  disabled,
}: {
  matterId: string;
  value: ApiResearchSelection | null;
  onChange: (value: ApiResearchSelection | null) => void;
  disabled: boolean;
}) {
  const t = useTranslations("matterAssistant");
  const getToken = useTokenProvider();
  const id = useId();
  const [rows, setRows] = useState<ApiMatterTransaction[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    onChange(null);
    try {
      const all: ApiMatterTransaction[] = [];
      const seen = new Set<string>();
      let cursor: string | undefined;
      do {
        const page = await listTransactions(getToken, matterId, {
          limit: 100,
          cursor,
        });
        all.push(...page.items);
        if (page.page.hasMore && !page.page.nextCursor)
          throw new Error("Incomplete transaction list");
        cursor = page.page.hasMore
          ? (page.page.nextCursor ?? undefined)
          : undefined;
        if (cursor && seen.has(cursor))
          throw new Error("Repeated transaction page");
        if (cursor) seen.add(cursor);
      } while (cursor && seen.size < 100);
      if (cursor) throw new Error("Incomplete transaction list");
      setRows(all);
      setError(false);
    } catch {
      setRows([]);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [getToken, matterId, onChange]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="border-border mb-3 space-y-2 border-t pt-3">
      <label htmlFor={id} className="text-muted-ink block text-xs">
        {t("legalTransaction")}
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <select
          id={id}
          className="border-border-control bg-surface focus-visible:outline-ring rounded-control min-h-10 min-w-0 flex-1 border px-3 text-sm focus-visible:outline-2"
          disabled={disabled || loading || error}
          value={
            value ? `${value.transactionId}:${value.associationVersion}` : ""
          }
          onChange={(event) => {
            const row = rows.find(
              (item) => `${item.id}:${item.version}` === event.target.value,
            );
            onChange(
              row
                ? { transactionId: row.id, associationVersion: row.version }
                : null,
            );
          }}
        >
          <option value="">{t("chooseLegalTransaction")}</option>
          {rows.map((row) => (
            <option key={row.id} value={`${row.id}:${row.version}`}>
              {t("legalTransactionNumber", {
                number: row.ordinal,
                version: row.version,
              })}
            </option>
          ))}
        </select>
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || loading}
          onClick={() => void load()}
        >
          {t("refreshLegalTransactions")}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-red text-sm">
          {t("legalTransactionsUnavailable")}
        </p>
      )}
    </div>
  );
}
function coverageMessageKey(reason: string) {
  switch (reason) {
    case "requested-authority-missing":
      return "legalCoverageReasons.requestedAuthorityMissing";
    case "authority-metadata-unsupported":
      return "legalCoverageReasons.authorityMetadataUnsupported";
    case "source-passages-withheld":
      return "legalCoverageReasons.sourcePassagesWithheld";
    case "source-release-unavailable":
      return "legalCoverageReasons.sourceReleaseUnavailable";
    case "quotation-boundary-unavailable":
      return "legalCoverageReasons.quotationBoundaryUnavailable";
    default:
      return "legalCoverageUnavailable";
  }
}
export function LegalResultContext({
  context,
  matterId,
  onSelect,
}: {
  context: ApiLegalContext;
  matterId: string;
  onSelect: (value: LegalSourceSelection) => void;
}) {
  const t = useTranslations("matterAssistant");
  const dates = context.dateContext;
  const coverageKeys = [
    ...new Set(context.coverageGaps.map(coverageMessageKey)),
  ];
  return (
    <section
      className="border-border mt-3 space-y-2 rounded border p-3 text-sm"
      aria-label={t("legalContext")}
    >
      <h4 className="font-semibold">{t("legalContext")}</h4>
      {dates && (
        <>
          <p>{t("legalCurrentDate", { date: dates.currentDate })}</p>
          <p>
            {t("legalTransactionDate", {
              date: dates.transactionDate ?? t("legalUnknown"),
            })}
          </p>
          {dates.transactionId && (
            <p className="text-muted-ink break-words text-xs">
              {t("legalScopePin", {
                id: dates.transactionId,
                version: dates.associationVersion ?? t("legalUnknown"),
              })}
            </p>
          )}
          {dates.factId && (
            <p className="text-muted-ink break-words text-xs">
              {t("legalFactPin", {
                id: dates.factId,
                version: dates.factVersion ?? t("legalUnknown"),
              })}
            </p>
          )}
          {dates.reason !== "reviewed-date" && (
            <p className="text-amber-text flex items-start gap-2">
              <AlertTriangle className="size-4 shrink-0" />
              <span>
                {t("legalDateInputRequired")}{" "}
                <Link className="underline" href={`/matters/${matterId}/facts`}>
                  {t("legalReviewFacts")}
                </Link>
              </span>
            </p>
          )}
        </>
      )}
      {context.sourceReleaseVersion && (
        <p className="text-muted-ink break-all text-xs">
          {t("legalSourceRelease", { version: context.sourceReleaseVersion })}
        </p>
      )}
      {!!coverageKeys.length && (
        <div className="text-amber-text flex items-start gap-2">
          <AlertTriangle className="size-4 shrink-0" />
          <ul className="space-y-1">
            {coverageKeys.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
        </div>
      )}
      {context.visibility === "current-policy-unavailable" && (
        <p>{t("legalHistoryUnavailable")}</p>
      )}
      {!!context.authorities.length && (
        <>
          <p className="font-medium">{t("legalSourceLeads")}</p>
          <div className="flex flex-wrap gap-2">
            {context.authorities.map((authority) => (
              <button
                type="button"
                key={authority.sourceId}
                onClick={() => onSelect(lead(authority, context))}
                className="border-border-strong text-forest focus-visible:outline-ring rounded-control border px-3 py-1 text-xs focus-visible:outline-2"
              >
                {authority.reference || authority.title}
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
export function LegalAuthorityPanel({
  selection,
  matterId,
  onSelect,
}: {
  selection: LegalSourceSelection;
  matterId: string;
  onSelect: (value: LegalSourceSelection) => void;
}) {
  const t = useTranslations("matterAssistant");
  const authority = selection.authorityMetadata;
  if (!authority) return null;
  const url = officialUrl(authority.sourceUrl);
  const reviewKey = [
    "discovered",
    "provenance-recorded",
    "rights-reviewed",
    "content-reviewed",
    "approved",
    "quarantined",
    "retired",
  ].includes(authority.reviewState)
    ? authority.reviewState
    : "unknown";
  return (
    <div className="mt-3 space-y-2 text-sm">
      <p className="font-medium">{t(`legalKinds.${authority.kind}`)}</p>
      {selection.metadataLead && (
        <p className="text-muted-ink">{t("legalMetadataLead")}</p>
      )}
      <p>
        {t("legalSourceReview", { state: t(`legalReviewStates.${reviewKey}`) })}
      </p>
      <p>
        {t("legalCurrency", {
          state: t(`legalCurrencyStates.${authority.currencyStatus}`),
        })}
      </p>
      <p>
        {t("legalPublicationDate", {
          date: authority.publicationDate ?? t("legalUnknown"),
        })}
      </p>
      <p>
        {t("legalEffectiveFrom", {
          date: authority.commencementKnown
            ? (authority.effectiveFrom ?? t("legalUnknown"))
            : t("legalUnknown"),
        })}
      </p>
      <p>
        {t("legalEffectiveTo", {
          date: authority.effectiveTo ?? t("legalUnknown"),
        })}
      </p>
      {!authority.commencementKnown && (
        <p className="text-amber-text flex gap-2">
          <AlertTriangle className="size-4 shrink-0" />
          {t("legalCommencementUnknown")}
        </p>
      )}
      {authority.commencementSourceId && (
        <p className="break-words text-xs">
          {t("legalCommencementSource", {
            source: authority.commencementSourceId,
            page: authority.commencementPage ?? t("legalUnknown"),
          })}
        </p>
      )}
      <p className="text-muted-ink text-xs">{t("legalTemporalNotice")}</p>
      <p className="text-muted-ink break-all text-xs">
        {t("sourceVersion", { version: authority.releaseVersion })}
      </p>
      <details className="text-muted-ink text-xs">
        <summary>{t("legalSourceFingerprint")}</summary>
        <code className="break-all">{authority.sourceSha256}</code>
      </details>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-forest inline-flex items-center gap-1 underline"
        >
          {t("legalOfficialSource")}
          <ExternalLink className="size-4" />
        </a>
      )}
      {!!authority.relationships.length && (
        <ul className="space-y-2">
          {authority.relationships.map((relation, index) => {
            const target = selection.legalContext?.authorities.find(
              (item) => item.sourceId === relation.targetSourceId,
            );
            return (
              <li key={`${relation.targetSourceId}-${index}`}>
                <span>{t(`legalRelations.${relation.relation}`)} </span>
                {target ? (
                  <button
                    type="button"
                    className="text-forest underline"
                    onClick={() =>
                      onSelect(lead(target, selection.legalContext))
                    }
                  >
                    {relation.targetReference ?? target.reference}
                  </button>
                ) : (
                  <span>
                    {relation.targetReference ?? relation.targetSourceId}
                  </span>
                )}
                <span className="text-muted-ink block text-xs">
                  {t("legalRelationshipLocator", {
                    page: relation.supportingPage ?? t("legalUnknown"),
                    state: t(`legalRelationshipReview.${relation.reviewState}`),
                  })}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {selection.legalContext && (
        <LegalResultContext
          context={selection.legalContext}
          matterId={matterId}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}
