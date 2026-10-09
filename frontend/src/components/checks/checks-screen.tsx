"use client";

import {
  AlertCircle,
  CheckCircle,
  Circle,
  Info,
  LoaderCircle,
  type LucideIcon,
  Minus,
  ShieldAlert,
  Triangle,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  ApiError,
  isApiEnabled,
  type TokenProvider,
  apiErrorMessage,
} from "@/lib/api/client";
import {
  listCheckResults,
  listCompleteIssues,
  type RunChecksBody,
  recordIssueDecision,
  runChecks,
} from "@/lib/api/checks";
import { RequirementsPanel } from "@/components/matter/requirements-panel";
import { CheckScopeSelector } from "./check-scope-selector";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { useDemoStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type {
  ApiCheckResult,
  ApiIssueGates,
  ApiLegalIssue,
  CheckOutcome,
  IssueSeverity,
  IssueState,
} from "@/types/rta";
import type { Check } from "@/types/check";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

/**
 * Entry point: split between API-bound and demo modes using the same pattern
 * as new-matter-screen.tsx. Hooks must stay unconditional within the component.
 */
export function ChecksScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundChecksScreen matterId={matterId} />
  ) : (
    <DemoChecksScreen matterId={matterId} />
  );
}

function ApiBoundChecksScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  return <ChecksScreenContent matterId={matterId} getToken={getToken} />;
}

function DemoChecksScreen({ matterId }: { matterId: string }) {
  const checks = useDemoStore((state) => state.checks);
  return (
    <DemoChecksContent
      matterId={matterId}
      checks={checks.filter((check) => check.matterId === matterId)}
    />
  );
}

interface ChecksScreenContentProps {
  matterId: string;
  getToken: TokenProvider;
}

function ChecksScreenContent({ matterId, getToken }: ChecksScreenContentProps) {
  const t = useTranslations("checks");
  const tRoot = useTranslations();

  // State for issues and gates
  const [issues, setIssues] = useState<ApiLegalIssue[]>([]);
  const [gates, setGates] = useState<ApiIssueGates | null>(null);
  const [checkResults, setCheckResults] = useState<ApiCheckResult[]>([]);
  const [resultCursor, setResultCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const tScope = useTranslations("checkScope");

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningChecks, setRunningChecks] = useState(false);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<IssueSeverity | "">("");
  const [stateFilter, setStateFilter] = useState<IssueState | "">("");

  // Issue resolution modal
  const [selectedIssue, setSelectedIssue] = useState<ApiLegalIssue | null>(
    null,
  );
  const [targetState, setTargetState] = useState<IssueState | "">("");
  const [reason, setReason] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const reasonInputRef = useRef<HTMLTextAreaElement>(null);

  const [scope, setScope] = useState<RunChecksBody | null>(null);
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [issuesResult, resultsResult] = await Promise.all([
        listCompleteIssues(getToken, matterId),
        listCheckResults(getToken, matterId, {}),
      ]);
      setIssues(issuesResult.items);
      setGates(issuesResult.gates);
      setCheckResults(resultsResult.items);
      setResultCursor(resultsResult.page.nextCursor);
    } catch (cause) {
      setError(apiErrorMessage(cause, t("loadError")));
    } finally {
      setLoading(false);
    }
  }, [getToken, matterId, t]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const loadMore = async () => {
    if (!resultCursor) return;
    setLoadingMore(true);
    try {
      const page = await listCheckResults(getToken, matterId, {
        cursor: resultCursor,
      });
      if (page.page.nextCursor === resultCursor)
        throw new Error(t("loadError"));
      setCheckResults((rows) => [
        ...rows,
        ...page.items.filter(
          (row) => !rows.some((existing) => existing.id === row.id),
        ),
      ]);
      setResultCursor(page.page.nextCursor);
    } catch (cause) {
      setError(apiErrorMessage(cause, t("loadError")));
    } finally {
      setLoadingMore(false);
    }
  };

  // Run checks
  const handleRunChecks = useCallback(async () => {
    if (!scope) return;
    setRunningChecks(true);
    setError(null);
    try {
      await runChecks(getToken, matterId, scope);
      await fetchData();
    } catch (cause) {
      if (cause instanceof ApiError && [409, 412].includes(cause.status))
        setScope(null);
      setError(apiErrorMessage(cause, t("runError")));
    } finally {
      setRunningChecks(false);
    }
  }, [getToken, matterId, t, scope, fetchData]);

  // Record issue decision
  const handleRecordDecision = useCallback(async () => {
    if (!selectedIssue || !targetState) return;
    setSubmittingDecision(true);
    setError(null);
    try {
      const updatedIssue = await recordIssueDecision(
        getToken,
        matterId,
        selectedIssue.id,
        {
          state: targetState,
          ...(reason.trim() ? { reason: reason.trim() } : {}),
        },
        selectedIssue.version,
      );
      setIssues((current) =>
        current.map((issue) =>
          issue.id === updatedIssue.id ? updatedIssue : issue,
        ),
      );
      setSelectedIssue(null);
      setTargetState("");
      setReason("");
      await fetchData();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setError(t("conflictError"));
      } else {
        setError(apiErrorMessage(cause, t("decisionError")));
      }
    } finally {
      setSubmittingDecision(false);
    }
  }, [selectedIssue, targetState, reason, getToken, matterId, t, fetchData]);

  // Filter issues
  const filteredIssues = issues.filter((issue) => {
    if (severityFilter && issue.severity !== severityFilter) return false;
    if (stateFilter && issue.state !== stateFilter) return false;
    return true;
  });

  // Modal state management
  useEffect(() => {
    if (selectedIssue !== null) {
      reasonInputRef.current?.focus();
    }
  }, [selectedIssue]);

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <RequirementsPanel
          getToken={getToken}
          matterId={matterId}
          mode="checks"
        />
        <CheckScopeSelector
          getToken={getToken}
          matterId={matterId}
          value={scope}
          onChange={setScope}
        />
        {/* Gates Summary Bar */}
        {gates && (
          <section className="rounded-card border-border bg-surface mb-6 border p-4">
            <h2 className="text-muted-ink text-xs font-semibold">
              {t("gateSummary")}
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <GateBadge
                label={t("draftGeneration")}
                blocked={gates.blocksDraftGeneration}
              />
              <GateBadge label={t("approval")} blocked={gates.blocksApproval} />
              <GateBadge
                label={t("registrationExport")}
                blocked={gates.blocksRegistrationReadyExport}
              />
            </div>
            {(gates.openStatutoryBlockerIds.length > 0 ||
              gates.openBlockingIssueIds.length > 0) && (
              <div className="mt-3 grid gap-2 text-sm">
                {gates.openStatutoryBlockerIds.length > 0 && (
                  <div className="flex items-center gap-2">
                    <ShieldAlert
                      className="size-4 shrink-0"
                      strokeWidth={1.5}
                    />
                    <span>
                      {t("statutoryBlockers", {
                        count: gates.openStatutoryBlockerIds.length,
                      })}
                    </span>
                  </div>
                )}
                {gates.openBlockingIssueIds.length > 0 && (
                  <div className="flex items-center gap-2">
                    <AlertCircle
                      className="size-4 shrink-0"
                      strokeWidth={1.5}
                    />
                    <span>
                      {t("blockingIssues", {
                        count: gates.openBlockingIssueIds.length,
                      })}
                    </span>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* Run Checks Button */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("issuesHeading")}</h2>
          <Button
            variant="primary"
            disabled={runningChecks || !scope}
            onClick={() => void handleRunChecks()}
          >
            {runningChecks ? (
              <>
                <LoaderCircle
                  className="size-4 animate-spin"
                  strokeWidth={1.5}
                />
                {t("runningChecks")}
              </>
            ) : (
              t("runChecks")
            )}
          </Button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="border-red bg-red-bg text-red mb-6 rounded border p-3 text-sm">
            <div className="flex items-start gap-2">
              <AlertCircle className="size-5 shrink-0" strokeWidth={1.5} />
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="py-8 text-center">
            <LoaderCircle
              className="text-muted-ink mx-auto size-6 animate-spin"
              strokeWidth={1.5}
            />
            <p className="text-muted-ink mt-2 text-sm">{t("loading")}</p>
          </div>
        )}

        {/* Filters */}
        {!loading && (
          <>
            <div className="mb-4 flex flex-wrap gap-3">
              <FilterSelect
                label={t("filterBySeverity")}
                value={severityFilter}
                onChange={(v: string) =>
                  setSeverityFilter(v as IssueSeverity | "")
                }
                options={[
                  "",
                  "INFORMATION",
                  "WARNING",
                  "HIGH_RISK",
                  "BLOCKING",
                ]}
                getLabel={(v) => {
                  if (v === "") return t("allSeverities");
                  return t(`severity.${v}`);
                }}
              />
              <FilterSelect
                label={t("filterByState")}
                value={stateFilter}
                onChange={(v: string) => setStateFilter(v as IssueState | "")}
                options={[
                  "",
                  "OPEN",
                  "TRIAGED",
                  "ACTION_REQUIRED",
                  "RESOLVED",
                  "ACCEPTED_RISK",
                  "FALSE_POSITIVE",
                  "OUTSIDE_SCOPE",
                ]}
                getLabel={(v) => {
                  if (v === "") return t("allStates");
                  return t(`state.${v}`);
                }}
              />
            </div>

            {/* Issues List */}
            {filteredIssues.length === 0 ? (
              <p className="text-muted-ink py-6 text-center text-sm">
                {issues.length === 0 ? t("noIssues") : t("noMatching")}
              </p>
            ) : (
              <div className="space-y-3">
                {filteredIssues.map((issue) => (
                  <IssueRow
                    key={issue.id}
                    issue={issue}
                    t={t}
                    tRoot={tRoot}
                    onSelectDecision={() => {
                      setSelectedIssue(issue);
                      setTargetState("");
                      setReason("");
                    }}
                  />
                ))}
              </div>
            )}

            {/* Check Results (optional, lower priority) */}
            {checkResults.length > 0 && (
              <section className="border-border mt-8 border-t pt-8">
                <h3 className="text-lg font-semibold">{t("checkResults")}</h3>
                <div className="mt-3 space-y-2">
                  {checkResults.map((result) => (
                    <div
                      key={result.id}
                      className="border-border-strong bg-surface flex items-start gap-3 rounded border p-3"
                    >
                      <CheckResultIcon outcome={result.outcome} />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">
                          {tRoot(result.explanationKey)}
                        </div>
                        <ScopeHistory value={result} />
                        {result.provisional && (
                          <div className="text-muted-ink mt-1 text-xs">
                            {t("provisionalNote")}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                {resultCursor && (
                  <Button
                    variant="secondary"
                    disabled={loadingMore}
                    onClick={() => void loadMore()}
                  >
                    {tScope("more")}
                  </Button>
                )}
              </section>
            )}
          </>
        )}
      </div>

      {/* Issue Decision Modal */}
      {selectedIssue && (
        <IssueDecisionModal
          issue={selectedIssue}
          targetState={targetState}
          reason={reason}
          submitting={submittingDecision}
          onTargetStateChange={setTargetState}
          onReasonChange={setReason}
          onCancel={() => setSelectedIssue(null)}
          onSubmit={() => void handleRecordDecision()}
          reasonInputRef={reasonInputRef}
          t={t}
          tRoot={tRoot}
        />
      )}
    </AppShell>
  );
}

/* ── Demo mode fallback ─────────────────────────────────────────────────── */

interface DemoChecksContentProps {
  matterId: string;
  checks: Check[];
}

function DemoChecksContent({ matterId, checks }: DemoChecksContentProps) {
  const t = useTranslations("checks");
  const tRoot = useTranslations();
  const resolveCheck = useDemoStore((state) => state.resolveCheck);

  const [resolution, setResolution] = useState<{
    check: Check;
    action: string;
  }>();
  const [reason, setReason] = useState("");
  const reasonInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (resolution) reasonInputRef.current?.focus();
  }, [resolution]);

  const record = () => {
    if (!resolution || !reason.trim()) return;
    resolveCheck(
      resolution.check.id,
      resolution.action as
        | "resolved"
        | "waived"
        | "document-requested"
        | "checklist-created",
      reason,
    );
    setResolution(undefined);
    setReason("");
  };

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <p className="text-muted-ink text-sm">{t("demoMode")}</p>
        <div className="mt-4 space-y-4">
          {checks.map((check) => (
            <div
              key={check.id}
              className="border-border bg-surface rounded-card border p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 space-y-2">
                  <StatusBadge status={check.status} />
                  <h3 className="font-semibold">
                    {tRoot(check.descriptionKey)}
                  </h3>
                  <p className="text-muted-ink text-sm">
                    {tRoot(check.suggestedResolutionKey)}
                  </p>
                </div>
                <Button
                  onClick={() => setResolution({ check, action: "resolved" })}
                >
                  {t("resolve")}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {resolution && (
        <div
          className="bg-scrim fixed inset-0 z-40 grid place-items-center p-4"
          role="presentation"
          onKeyDown={(event) => {
            if (event.key === "Escape") setResolution(undefined);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="resolution-title"
            className="rounded-dialog border-border-strong bg-surface shadow-dialog w-full max-w-lg border p-5"
          >
            <h2 id="resolution-title" className="text-2xl font-semibold">
              {t("resolutionTitle")}
            </h2>
            <label className="mt-4 block font-medium">
              {t("reason")}
              <textarea
                ref={reasonInputRef}
                className="border-border-control mt-1 min-h-28 w-full rounded border p-3"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <Button onClick={() => setResolution(undefined)}>
                {t("cancel")}
              </Button>
              <Button
                variant="primary"
                disabled={!reason.trim()}
                onClick={record}
              >
                {t("record")}
              </Button>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}

/* ── Presentational components ────────────────────────────────────────── */

function GateBadge({ label, blocked }: { label: string; blocked: boolean }) {
  const t = useTranslations("checkScope");
  return (
    <div
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-2 rounded border p-3 text-sm",
        blocked
          ? "border-red bg-red-bg text-red"
          : "border-forest bg-soft-green text-forest",
      )}
    >
      {blocked ? (
        <ShieldAlert className="size-4 shrink-0" strokeWidth={1.5} />
      ) : (
        <CheckCircle className="size-4 shrink-0" strokeWidth={1.5} />
      )}
      <span className="font-medium">{label}</span>
      <span className="font-semibold">
        {t(blocked ? "gateBlocked" : "gateClear")}
      </span>
    </div>
  );
}

function ScopeHistory({
  value,
}: {
  value: {
    transactionId?: string | null;
    subjectId?: string | null;
    associationVersion?: number | null;
  };
}) {
  const t = useTranslations("checkScope");
  return (
    <p className="text-muted-ink mt-1 break-words text-xs leading-5">
      {value.transactionId ? (
        <>
          {t("history")}: {value.transactionId} &middot;{" "}
          {value.subjectId ?? t("transactionFacts")} &middot;{" "}
          {t("version", { version: value.associationVersion ?? 0 })}
        </>
      ) : (
        t("unscoped")
      )}
    </p>
  );
}

interface IssueRowProps {
  issue: ApiLegalIssue;
  t: (key: string) => string;
  tRoot: (key: string) => string;
  onSelectDecision: () => void;
}

function IssueRow({ issue, t, tRoot, onSelectDecision }: IssueRowProps) {
  const SeverityIcon = SEVERITY_ICONS[issue.severity];
  const stateLabel = t(`state.${issue.state}`);

  return (
    <div className="border-border bg-surface rounded border p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="border-border-strong inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold">
              <SeverityIcon className="size-3" strokeWidth={2} />
              {t(`severity.${issue.severity}`)}
            </div>
            <div className="border-border-strong inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold">
              <Circle className="size-2.5" fill="currentColor" />
              {stateLabel}
            </div>
          </div>
          <h3 className="mt-2 font-semibold">{tRoot(issue.summaryKey)}</h3>
          <ScopeHistory value={issue} />
          {issue.blockerKind && (
            <p className="text-muted-ink text-sm">
              {t(`blocker.${issue.blockerKind}`)}
            </p>
          )}
          {issue.resolutionReason && (
            <div className="border-forest bg-soft-green mt-2 rounded border-l-2 p-2 text-sm">
              {issue.resolutionReason}
            </div>
          )}
        </div>
        {issue.permittedStates.length > 0 && issue.state !== "RESOLVED" && (
          <Button
            variant="primary"
            className="shrink-0"
            onClick={onSelectDecision}
          >
            {t("recordDecision")}
          </Button>
        )}
      </div>
    </div>
  );
}

interface IssueDecisionModalProps {
  issue: ApiLegalIssue;
  targetState: IssueState | "";
  reason: string;
  submitting: boolean;
  onTargetStateChange: (state: IssueState | "") => void;
  onReasonChange: (reason: string) => void;
  onCancel: () => void;
  onSubmit: () => Promise<void> | void;
  reasonInputRef: React.RefObject<HTMLTextAreaElement | null>;
  t: (key: string) => string;
  tRoot: (key: string) => string;
}

function IssueDecisionModal({
  issue,
  targetState,
  reason,
  submitting,
  onTargetStateChange,
  onReasonChange,
  onCancel,
  onSubmit,
  reasonInputRef,
  t,
  tRoot,
}: IssueDecisionModalProps) {
  const reasonNeeded =
    targetState === "ACCEPTED_RISK" || targetState === "FALSE_POSITIVE";

  return (
    <div
      className="bg-scrim fixed inset-0 z-40 grid place-items-center p-4"
      role="presentation"
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="decision-title"
        className="rounded-dialog border-border-strong bg-surface shadow-dialog w-full max-w-lg border p-5"
      >
        <h2 id="decision-title" className="text-2xl font-semibold">
          {t("recordDecision")}
        </h2>
        <p className="text-muted-ink mt-1 text-sm">{tRoot(issue.summaryKey)}</p>

        <div className="mt-4">
          <label className="block font-medium">
            {t("targetState")}
            <select
              value={targetState}
              onChange={(e) =>
                onTargetStateChange(e.target.value as IssueState | "")
              }
              className="border-border-control bg-surface rounded-control mt-1 w-full border p-2"
            >
              <option value="">{t("selectState")}</option>
              {issue.permittedStates.map((state) => (
                <option key={state} value={state}>
                  {t(`state.${state}`)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {reasonNeeded && (
          <div className="mt-4">
            <label className="block font-medium">
              {t("reason")}
              <textarea
                ref={reasonInputRef}
                className="border-border-control mt-1 min-h-24 w-full rounded border p-2"
                value={reason}
                onChange={(e) => onReasonChange(e.target.value)}
                placeholder={t("reasonPlaceholder")}
              />
            </label>
          </div>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <Button onClick={onCancel} disabled={submitting}>
            {t("cancel")}
          </Button>
          <Button
            variant="primary"
            disabled={
              !targetState || (reasonNeeded && !reason.trim()) || submitting
            }
            onClick={() => void onSubmit()}
          >
            {submitting ? t("submitting") : t("record")}
          </Button>
        </div>
      </section>
    </div>
  );
}

interface FilterSelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  getLabel: (value: string) => string;
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  getLabel,
}: FilterSelectProps) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <label htmlFor={id} className="text-sm font-medium">
        {label}:
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border-border-control bg-surface rounded-control max-w-full border px-2 py-1 text-sm"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {getLabel(option)}
          </option>
        ))}
      </select>
    </div>
  );
}

interface CheckResultIconProps {
  outcome: CheckOutcome;
}

function CheckResultIcon({ outcome }: CheckResultIconProps) {
  switch (outcome) {
    case "PASS":
      return (
        <CheckCircle
          className="text-forest size-4 shrink-0"
          strokeWidth={1.5}
        />
      );
    case "FAIL":
      return (
        <AlertCircle className="text-red size-4 shrink-0" strokeWidth={1.5} />
      );
    case "INCONCLUSIVE":
      return <Minus className="size-4 shrink-0" strokeWidth={1.5} />;
    case "NOT_RUN":
      return <Circle className="size-4 shrink-0" strokeWidth={1.5} />;
  }
}

const SEVERITY_ICONS: Record<IssueSeverity, LucideIcon> = {
  INFORMATION: Info,
  WARNING: Triangle,
  HIGH_RISK: AlertCircle,
  BLOCKING: ShieldAlert,
};
