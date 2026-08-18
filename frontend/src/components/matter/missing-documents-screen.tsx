"use client";

import {
  AlertCircle,
  FileQuestion,
  LoaderCircle,
  AlertTriangle,
  AlertOctagon,
} from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ApiError, isApiEnabled } from "@/lib/api/client";
import { getMatter } from "@/lib/api/matters";
import { listIssues } from "@/lib/api/checks";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import type { ApiLegalIssue } from "@/types/rta";

export function MissingDocumentsScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundMissingDocumentsScreen matterId={matterId} />
  ) : (
    <OfflineMissingDocumentsScreen matterId={matterId} />
  );
}

function ApiBoundMissingDocumentsScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  const t = useTranslations("missingDocuments");
  const [hasChecklist, setHasChecklist] = useState(false);
  const [issues, setIssues] = useState<ApiLegalIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        // Fetch matter to check if checklist exists
        const matter = await getMatter(getToken, matterId);
        if (!cancelled) {
          setHasChecklist(matter.activeChecklistSnapshotId !== null);
        }

        // Fetch issues filtered for EVIDENCE blockers
        const issuesResult = await listIssues(getToken, matterId, {
          severity: "BLOCKING",
        });

        if (!cancelled) {
          // Filter to only evidence-blocking issues
          const evidenceIssues = issuesResult.items.filter(
            (issue) => issue.blockerKind === "EVIDENCE"
          );
          setIssues(evidenceIssues);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof ApiError ? cause.message : t("error"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchData();
    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="flex items-center justify-center gap-2 p-12">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          <span>{t("loading")}</span>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="border-red bg-red-bg text-red m-6 flex gap-3 rounded border p-4">
          <AlertCircle className="size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <span>{error}</span>
        </div>
      </AppShell>
    );
  }

  if (!hasChecklist) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="p-6">
          <div className="border-border-strong bg-surface rounded border p-6 text-center">
            <FileQuestion
              className="mx-auto size-12 text-muted-ink"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <h2 className="mt-4 text-lg font-semibold">{t("noChecklistEmpty")}</h2>
            <p className="text-muted-ink mt-2">{t("noChecklistEmptyBody")}</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (issues.length === 0) {
    return (
      <AppShell matterId={matterId}>
        <PageHeader title={t("title")} description={t("description")} />
        <div className="p-6">
          <div className="border-border-strong bg-selected-bg rounded border p-6 text-center">
            <AlertCircle
              className="mx-auto size-12 text-forest"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <h2 className="mt-4 text-lg font-semibold">{t("noIssues")}</h2>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link
                href={`/matters/${matterId}/documents`}
                className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
              >
                {t("uploadDocuments")}
              </Link>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <h2 className="text-lg font-semibold">{t("issuesList")}</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[1000px] border-collapse text-sm">
            <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs font-semibold uppercase">
              <tr className="border-border h-10 border-b">
                <th className="px-3 text-left">Issue</th>
                <th className="px-3 text-left">{t("issueSeverity")}</th>
                <th className="px-3 text-left">{t("issueState")}</th>
                <th className="px-3 text-left">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-border divide-y">
              {issues.map((issue) => (
                <IssueRow key={issue.id} issue={issue} />
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          <Link
            href={`/matters/${matterId}/documents`}
            className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
          >
            {t("uploadDocuments")}
          </Link>
          <Link
            href={`/matters/${matterId}/checks`}
            className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
          >
            {t("viewAllIssues")}
          </Link>
        </div>
      </div>
    </AppShell>
  );
}

function IssueRow({ issue }: { issue: ApiLegalIssue }) {
  const SeverityIcon =
    issue.severity === "BLOCKING"
      ? AlertOctagon
      : issue.severity === "HIGH_RISK"
        ? AlertTriangle
        : AlertCircle;

  const severityColor =
    issue.severity === "BLOCKING"
      ? "text-red"
      : issue.severity === "HIGH_RISK"
        ? "text-amber-text"
        : "text-forest";

  const stateColor =
    issue.state === "OPEN"
      ? "border-red text-red"
      : issue.state === "ACTION_REQUIRED"
        ? "border-amber text-amber-text"
        : "border-forest text-forest";

  return (
    <tr className="border-border h-11 hover:bg-hover-bg">
      <td className="px-3">
        <div className="flex items-start gap-2">
          <SeverityIcon
            className={`mt-0.5 size-4 shrink-0 ${severityColor}`}
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <span className="font-medium">{issue.issueTypeId}</span>
        </div>
      </td>
      <td className="px-3 text-sm">{issue.severity}</td>
      <td className="px-3">
        <span
          className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${stateColor}`}
        >
          {issue.state}
        </span>
      </td>
      <td className="px-3 text-sm text-muted-ink">
        {issue.evidenceReferenceIds.length > 0
          ? `${issue.evidenceReferenceIds.length} reference(s)`
          : "—"}
      </td>
    </tr>
  );
}

function OfflineMissingDocumentsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("missingDocuments");

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="border-border-strong bg-surface rounded border p-6 text-center">
          <FileQuestion
            className="mx-auto size-12 text-muted-ink"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <h2 className="mt-4 text-lg font-semibold">{t("noChecklistEmpty")}</h2>
          <p className="text-muted-ink mt-2">{t("noChecklistEmptyBody")}</p>
        </div>
      </div>
    </AppShell>
  );
}
