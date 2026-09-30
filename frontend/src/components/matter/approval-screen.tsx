"use client";

import {
  AlertCircle,
  Check,
  CheckCircle2,
  CircleDashed,
  LoaderCircle,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { ApiError, isApiEnabled, type TokenProvider, apiErrorMessage } from "@/lib/api/client";
import { createApproval, listApprovals } from "@/lib/api/approvals";
import { getForm } from "@/lib/api/drafts";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import type { ApiApprovalList, ApiGeneratedForm } from "@/types/rta";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";

export function ApprovalScreen({
  matterId,
  draftId,
}: {
  matterId: string;
  draftId: string;
}) {
  return isApiEnabled() ? (
    <ApiBoundApprovalScreen matterId={matterId} formId={draftId} />
  ) : (
    <DemoApprovalScreen matterId={matterId} draftId={draftId} />
  );
}

function ApiBoundApprovalScreen({
  matterId,
  formId,
}: {
  matterId: string;
  formId: string;
}) {
  const getToken = useTokenProvider();
  return <ApprovalScreenContent matterId={matterId} formId={formId} getToken={getToken} />;
}

function DemoApprovalScreen({
  matterId,
  draftId,
}: {
  matterId: string;
  draftId: string;
}) {
  return <DemoApprovalContent matterId={matterId} draftId={draftId} />;
}

interface ApprovalScreenContentProps {
  matterId: string;
  formId: string;
  getToken: TokenProvider;
}

function ApprovalScreenContent({
  matterId,
  formId,
  getToken,
}: ApprovalScreenContentProps) {
  const t = useTranslations("approval");
  const tRoot = useTranslations();
  const format = useFormatter();
  const codeLabel = useEnumLabel("enums.approvalGateCode");

  const [form, setForm] = useState<ApiGeneratedForm | null>(null);
  const [approvalList, setApprovalList] = useState<ApiApprovalList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [showDeclaration, setShowDeclaration] = useState(false);

  // Fetch form and approvals
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [formResult, approvalsResult] = await Promise.all([
        getForm(getToken, formId),
        listApprovals(getToken, formId),
      ]);
      setForm(formResult);
      setApprovalList(approvalsResult);
    } catch (cause) {
      setError(apiErrorMessage(cause, t("loadError")));
    } finally {
      setLoading(false);
    }
  }, [getToken, formId, t]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Handle approval
  const handleApprove = useCallback(async () => {
    if (!form || !approvalList) return;

    setApproving(true);
    setError(null);
    try {
      const result = await createApproval(getToken, formId, {
        disposedWarningIds: approvalList.gate.warnings.map((w) => w.id),
      });

      // Update form and approval list
      setForm({ ...form, state: "APPROVED", approvalId: result.approval.id });
      setApprovalList({
        ...approvalList,
        items: [result.approval, ...approvalList.items],
        gate: result.gate,
        currentApprovalId: result.approval.id,
      });
      setShowDeclaration(false);
    } catch (cause) {
      if (cause instanceof ApiError) {
        if (cause.status === 403) {
          setError(t("errorForbidden"));
        } else if (cause.status === 404) {
          setError(t("errorNotFound"));
        } else if (cause.status === 422) {
          setError(t("conflictError"));
        } else {
          setError(apiErrorMessage(cause, t("approveError")));
        }
      } else {
        setError(t("approveError"));
      }
    } finally {
      setApproving(false);
    }
  }, [form, approvalList, getToken, formId, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex items-center gap-2 p-6 text-muted-ink">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          {t("loading")}
        </div>
      </AppShell>
    );
  }

  if (!form || !approvalList) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex gap-3 rounded border border-red bg-red-bg p-6 text-sm text-red">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{t("loadError")}</p>
        </div>
      </AppShell>
    );
  }

  const gate = approvalList.gate;
  const canApprove = gate.approvalReady && !approving;
  const alreadyApproved = approvalList.currentApprovalId !== null;

  return (
    <AppShell matterId={matterId}>
      <div className="max-w-4xl">
        {/* Header */}
        <header className="border-border bg-surface border-b px-6 py-4">
          <h1 className="text-2xl font-semibold">{tRoot(form.titleKey)}</h1>
          <p className="text-muted-ink mt-2 text-sm">{t("description")}</p>
        </header>

        {/* Error message */}
        {error && (
          <div className="border-red bg-red-bg text-red mx-6 mt-6 flex gap-3 rounded border p-4 text-sm">
            <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
            <p>{error}</p>
          </div>
        )}

        {/* Approval gate section */}
        <section className="border-border border-t px-6 py-6">
          <h2 className="mb-4 text-lg font-semibold">{t("gateTitle")}</h2>

          {/* Approval ready status */}
          <div className="mb-6 rounded-card border border-border bg-surface p-4 shadow-card">
            <div className="flex items-center gap-3">
              {gate.approvalReady ? (
                <CheckCircle2 className="size-5 text-forest" strokeWidth={1.5} aria-hidden="true" />
              ) : (
                <CircleDashed className="size-5 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
              )}
              <span className="font-semibold">{t("readyLabel")}</span>
            </div>
          </div>

          {/* Blocking items */}
          {gate.blocking.length > 0 && (
            <div className="mb-6">
              <h3 className="mb-3 font-semibold text-red">{t("blockingTitle")}</h3>
              <ul className="space-y-2">
                {gate.blocking.map((item) => (
                  <div
                    key={item.code}
                    className="flex gap-3 rounded border border-red bg-red-bg p-3 text-sm"
                  >
                    <TriangleAlert
                      className="mt-0.5 size-4 shrink-0 text-red"
                      strokeWidth={1.5}
                      aria-hidden="true"
                    />
                    <div>
                      <div className="font-semibold">{codeLabel(item.code)}</div>
                      {tRoot.has(item.explanationKey) && (
                        <div className="text-muted-ink mt-1">{tRoot(item.explanationKey)}</div>
                      )}
                    </div>
                  </div>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {gate.warnings.length > 0 && (
            <div className="mb-6">
              <h3 className="mb-3 font-semibold text-amber-text">{t("warningsTitle")}</h3>
              <ul className="space-y-2">
                {gate.warnings.map((item) => (
                  <div
                    key={item.code}
                    className="flex gap-3 rounded border border-amber bg-amber-bg p-3 text-sm"
                  >
                    <TriangleAlert
                      className="mt-0.5 size-4 shrink-0 text-amber-text"
                      strokeWidth={1.5}
                      aria-hidden="true"
                    />
                    <div>
                      <div className="font-semibold">{codeLabel(item.code)}</div>
                      {tRoot.has(item.explanationKey) && (
                        <div className="text-muted-ink mt-1">{tRoot(item.explanationKey)}</div>
                      )}
                    </div>
                  </div>
                ))}
              </ul>
            </div>
          )}

          {/* Approval actions */}
          {!alreadyApproved && (
            <div>
              {!gate.approvalReady && (
                <p className="text-muted-ink mb-4 text-sm">
                  {t("resolveBefore")}{" "}
                  <Link
                    href={`/matters/${matterId}/drafts/${form.id}`}
                    className="underline hover:text-ink"
                  >
                    {t("resolveLink")}
                  </Link>{" "}
                  {t("resolveAfter")}
                </p>
              )}
              {showDeclaration ? (
                <div className="rounded-card border border-border bg-surface p-4 shadow-card">
                  <div className="mb-4 max-w-2xl space-y-3">
                    <label className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        defaultChecked
                        disabled
                        className="mt-1"
                      />
                      <span className="text-sm">{t("reviewAndApprove")}</span>
                    </label>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="primary"
                      disabled={!canApprove}
                      onClick={() => void handleApprove()}
                    >
                      {approving ? (
                        <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
                      ) : (
                        <Check className="size-4" strokeWidth={1.5} />
                      )}
                      {approving ? t("approvingButton") : t("approveButton")}
                    </Button>
                    <Button onClick={() => setShowDeclaration(false)}>
                      {t("cancel")}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="primary"
                  disabled={!canApprove}
                  onClick={() => setShowDeclaration(true)}
                >
                  <Check className="size-4" strokeWidth={1.5} />
                  {t("approveButton")}
                </Button>
              )}
            </div>
          )}
        </section>

        {/* Approval history section */}
        {approvalList.items.length > 0 && (
          <section className="border-border border-t px-6 py-6">
            <h2 className="mb-4 text-lg font-semibold">{t("approvalHistory")}</h2>
            <div className="space-y-3">
              {approvalList.items.map((approval) => (
                <div
                  key={approval.id}
                  className="flex items-start gap-4 rounded-card border border-border bg-surface p-4 text-sm shadow-card"
                >
                  <div className="flex-1">
                    <div className="font-semibold">{t("approver")}</div>
                    <div className="text-muted-ink text-xs">
                      {t("approvedAt")}: {format.dateTime(new Date(approval.createdAt), { dateStyle: "medium" })}
                    </div>

                    {approval.revokedByApprovalId && (
                      <div className="text-amber-text text-xs">
                        {t("revokedBy")}
                      </div>
                    )}
                  </div>
                  {approval.id === approvalList.currentApprovalId && !approval.revokedByApprovalId && (
                    <span className="inline-flex min-h-6 items-center gap-1 rounded-full border border-forest bg-soft-green px-2 text-xs font-semibold text-forest">
                      <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />
                      {t("current")}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Next action */}
        {alreadyApproved && (
          <section className="border-border border-t px-6 py-6">
            <div className="flex gap-3 rounded border border-forest bg-soft-green p-4">
              <CheckCircle2 className="size-5 text-forest shrink-0" strokeWidth={1.5} aria-hidden="true" />
              <div>
                <h3 className="font-semibold text-forest">{t("formApproved")}</h3>
                <p className="text-muted-ink mt-1 text-sm">
                  {t("formApprovedBody")}
                </p>
                <Link href={`/matters/${matterId}/exports`} className="mt-3 inline-block">
                  <Button variant="primary">
                    {t("nextAction")}
                  </Button>
                </Link>
              </div>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}

function DemoApprovalContent({
  matterId,
}: {
  matterId: string;
  draftId: string;
}) {
  const t = useTranslations("approval");
  return (
    <AppShell matterId={matterId}>
      <div className="rounded-card border border-border bg-surface p-6 shadow-card">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-muted-ink mt-2 text-sm">{t("demoUnavailable")}</p>
      </div>
    </AppShell>
  );
}
