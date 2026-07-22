"use client";

import { BookOpen, FileSearch, Scale, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { crossChecks } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import type { Check, CheckCategory } from "@/types";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

const groups: Array<{
  category: CheckCategory;
  key:
    | "missingDocument"
    | "identity"
    | "parcel"
    | "chainOfTitle"
    | "registration"
    | "stampDuty"
    | "execution"
    | "jurisdiction";
}> = [
  { category: "missing-document", key: "missingDocument" },
  { category: "identity", key: "identity" },
  { category: "parcel", key: "parcel" },
  { category: "chain-of-title", key: "chainOfTitle" },
  { category: "registration", key: "registration" },
  { category: "stamp-duty", key: "stampDuty" },
  { category: "execution", key: "execution" },
  { category: "jurisdiction", key: "jurisdiction" },
];

export function ChecksScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("checks");
  const allChecks = useDemoStore((state) => state.checks);
  const resolveCheck = useDemoStore((state) => state.resolveCheck);
  const checks = allChecks.filter((check) => check.matterId === matterId);
  const crossCheck = crossChecks.find((item) => item.matterId === matterId);
  const [resolution, setResolution] = useState<{
    check: Check;
    action: NonNullable<Check["resolution"]>["action"];
  }>();
  const [reason, setReason] = useState("");
  const reasonInputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (resolution) reasonInputRef.current?.focus();
  }, [resolution]);
  const [announcement, setAnnouncement] = useState("");
  const record = () => {
    if (!resolution || !reason.trim()) return;
    resolveCheck(resolution.check.id, resolution.action, reason);
    setResolution(undefined);
    setReason("");
    setAnnouncement(t("recorded"));
  };
  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="p-6">
        {crossCheck && (
          <section className="border-amber bg-amber-bg rounded border p-5">
            <div className="flex items-start gap-3">
              <Scale className="text-amber-text size-6" strokeWidth={1.5} />
              <div className="min-w-0 flex-1">
                <div className="text-amber-text text-xs font-semibold uppercase">
                  {t("crossCheck")}
                </div>
                <h2 className="mt-1 text-2xl font-semibold">
                  {t("extentTally")}
                </h2>
                <StatusBadge className="mt-2" status="warning" />
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {crossCheck.bindings.map((binding, index) => (
                <div
                  key={`${binding.factId}-${index}`}
                  className="border-border-strong bg-surface rounded border p-3"
                >
                  <div className="text-muted-ink text-xs font-semibold uppercase">
                    {t("binding")} {index + 1}
                  </div>
                  <div className="mt-1 font-medium">
                    {binding.evidence.documentId} ·{" "}
                    {t("page", { page: binding.evidence.page })}
                  </div>
                  <div className="mt-1 text-sm">{binding.evidence.snippet}</div>
                </div>
              ))}
            </div>
          </section>
        )}
        <div className="mt-6 space-y-6">
          {groups.map((group) => {
            const items = checks.filter(
              (check) => check.category === group.category,
            );
            return (
              <section
                key={group.category}
                aria-labelledby={`group-${group.category}`}
              >
                <h2
                  id={`group-${group.category}`}
                  className="text-2xl font-semibold"
                >
                  {t(group.key)}
                </h2>
                <div className="border-border bg-surface mt-2 overflow-hidden border-y">
                  {items.length === 0 ? (
                    <p className="text-muted-ink px-4 py-3 text-sm">
                      {t("emptyGroup")}
                    </p>
                  ) : (
                    items.map((check) => (
                      <div
                        key={check.id}
                        className="border-border grid gap-4 border-b p-4 last:border-b-0 lg:grid-cols-[1fr_280px]"
                      >
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusBadge status={check.status} />
                            <h3 className="font-heading text-xl font-semibold">
                              {t(
                                check.descriptionKey.split(".").at(-1) as
                                  | "identityPass"
                                  | "extentConflict"
                                  | "registryMissing"
                                  | "boundaryReview",
                              )}
                            </h3>
                          </div>
                          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                            <Meta
                              icon={<FileSearch strokeWidth={1.5} />}
                              term={t("affected")}
                              value={check.affectedFactIds.join(" · ") || "—"}
                            />
                            <Meta
                              icon={<BookOpen strokeWidth={1.5} />}
                              term={t("authority")}
                              value={check.authority?.reference ?? "—"}
                            />
                            <Meta
                              icon={<ShieldAlert strokeWidth={1.5} />}
                              term={t("suggested")}
                              value={t(
                                check.suggestedResolutionKey
                                  .split(".")
                                  .at(-1) as
                                  | "noAction"
                                  | "compareEvidence"
                                  | "requestDocument"
                                  | "reviewBoundary",
                              )}
                            />
                            <Meta
                              icon={<FileSearch strokeWidth={1.5} />}
                              term={t("owner")}
                              value={
                                check.ownerId
                                  ? t("syntheticOwner")
                                  : t("unassigned")
                              }
                            />
                          </dl>
                          {check.resolution && (
                            <div className="border-forest bg-soft-green mt-3 border-l-2 p-3 text-sm">
                              <strong>{t("history")}:</strong>{" "}
                              {check.resolution.reason}
                            </div>
                          )}
                        </div>
                        <div className="flex flex-wrap content-start gap-2 lg:justify-end">
                          {check.status !== "pass" && (
                            <>
                              <Button
                                variant="primary"
                                onClick={() =>
                                  setResolution({ check, action: "resolved" })
                                }
                              >
                                {t("resolve")}
                              </Button>
                              <Button
                                onClick={() =>
                                  setResolution({ check, action: "waived" })
                                }
                              >
                                {t("waive")}
                              </Button>
                              <Button
                                onClick={() =>
                                  setResolution({
                                    check,
                                    action: "document-requested",
                                  })
                                }
                              >
                                {t("requestDocument")}
                              </Button>
                              <Button
                                onClick={() =>
                                  setResolution({
                                    check,
                                    action: "checklist-created",
                                  })
                                }
                              >
                                {t("createItem")}
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </div>
      {resolution && (
        <div
          className="bg-ink/25 fixed inset-0 z-40 grid place-items-center p-4"
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
            <p className="text-muted-ink mt-2">
              {t(
                resolution.check.descriptionKey.split(".").at(-1) as
                  | "identityPass"
                  | "extentConflict"
                  | "registryMissing"
                  | "boundaryReview",
              )}
            </p>
            <label className="mt-4 block font-medium">
              {t("reason")}
              <textarea
                ref={reasonInputRef}
                className="border-border-strong mt-1 min-h-28 w-full rounded border p-3"
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

function Meta({
  icon,
  term,
  value,
}: {
  icon: React.ReactNode;
  term: string;
  value: string;
}) {
  return (
    <div>
      <dt className="text-muted-ink flex items-center gap-2 text-xs">
        <span
          aria-hidden="true"
          className="[&_svg]:size-4 [&_svg]:stroke-[1.5]"
        >
          {icon}
        </span>
        {term}
      </dt>
      <dd className="pl-6">{value}</dd>
    </div>
  );
}
