"use client";

import { ArrowRight, FilePlus2, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  FACT_SECTIONS,
  factLabelKey,
} from "@/lib/i18n/fact-label-keys";
import { templates } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import { deriveTemplateReadiness } from "@/lib/templates/readiness";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

const stateKeys = {
  working: "working",
  "in-review": "inReview",
  approved: "approved",
  exported: "exported",
} as const;

const approvedTemplates = templates.filter(
  (template) => template.approvalState === "approved",
);

export function DraftsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("draft");
  const tf = useTranslations("facts");
  const ts = useTranslations("sections");
  const allDrafts = useDemoStore((state) => state.drafts);
  const allFacts = useDemoStore((state) => state.facts);
  const createDraft = useDemoStore((state) => state.createDraft);
  const drafts = allDrafts.filter((draft) => draft.matterId === matterId);
  const [open, setOpen] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [templateId, setTemplateId] = useState(approvedTemplates[0]?.id ?? "");

  const facts = useMemo(
    () => allFacts.filter((fact) => fact.matterId === matterId),
    [allFacts, matterId],
  );
  const template = approvedTemplates.find((entry) => entry.id === templateId);
  const readiness = useMemo(
    () => (template ? deriveTemplateReadiness(template, facts) : undefined),
    [template, facts],
  );

  const generate = () => {
    if (!template) return;
    // The document keeps its own labels, so they are resolved here where the
    // locale lives rather than inside the store.
    const labels: Record<string, string> = {
      [template.nameKey]: t("form8Name"),
      "draft.fieldPending": t("fieldPending"),
    };
    for (const field of template.fields) {
      labels[field.labelKey] = tf(factLabelKey(field.labelKey));
    }
    for (const section of FACT_SECTIONS) {
      labels[`sections.${section}`] = ts(section);
    }
    const id = createDraft(matterId, template.id, labels);
    if (id) window.location.href = `/matters/${matterId}/drafts/${id}`;
    else setBlocked(true);
  };
  return (
    <AppShell matterId={matterId}>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          <Button
            variant="primary"
            onClick={() => {
              setOpen(true);
              setBlocked(false);
            }}
          >
            <FilePlus2 className="size-4" strokeWidth={1.5} />
            {t("newDraft")}
          </Button>
        }
      />
      <div className="p-6">
        <div className="border-border-strong bg-surface overflow-x-auto rounded border">
          <table className="w-full min-w-[900px] border-collapse whitespace-nowrap text-left">
            <thead className="bg-canvas text-muted-ink text-xs">
              <tr className="border-border h-10 border-b">
                <th className="px-4">{t("draftTitle")}</th>
                <th className="px-4">{t("template")}</th>
                <th className="px-4">{t("version")}</th>
                <th className="px-4">{t("state")}</th>
                <th className="px-4">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {drafts.map((draft) => (
                <tr
                  key={draft.id}
                  className="border-border h-11 border-b last:border-b-0"
                >
                  <td className="font-heading px-4 text-lg font-semibold">
                    {draft.title}
                  </td>
                  <td className="px-4">{t("form8Name")}</td>
                  <td className="px-4 tabular-nums">
                    v{draft.versions.length} ·{" "}
                    {
                      draft.versions.find(
                        (version) => version.id === draft.activeVersionId,
                      )?.hash
                    }
                  </td>
                  <td className="px-4">
                    <span className="border-border-strong inline-flex rounded-full border px-2 py-1 text-xs font-semibold">
                      {t(stateKeys[draft.approvalState])}
                    </span>
                  </td>
                  <td className="px-4">
                    <Link
                      className="border-border-strong hover:bg-hover-bg inline-flex min-h-8 items-center gap-2 rounded border px-3"
                      href={`/matters/${matterId}/drafts/${draft.id}`}
                    >
                      {t("open")}
                      <ArrowRight className="size-4" strokeWidth={1.5} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {open && (
        <div
          className="bg-ink/25 fixed inset-0 z-40 grid place-items-center p-4"
          role="presentation"
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-draft-title"
            className="rounded-dialog border-border-strong bg-surface shadow-dialog w-full max-w-xl border p-5"
          >
            <h2 id="new-draft-title" className="text-2xl font-semibold">
              {t("templatePicker")}
            </h2>
            {approvedTemplates.map((entry) => (
              <button
                key={entry.id}
                type="button"
                aria-pressed={entry.id === templateId}
                onClick={() => {
                  setTemplateId(entry.id);
                  setBlocked(false);
                }}
                className={`mt-4 block w-full rounded border p-4 text-left ${
                  entry.id === templateId
                    ? "border-forest bg-selected-bg"
                    : "border-border-strong hover:bg-hover-bg"
                }`}
              >
                <div className="text-forest text-xs font-semibold uppercase">
                  {t("approvedTemplate")}
                </div>
                <div className="font-heading mt-1 text-xl font-semibold">
                  {t("form8Name")}
                </div>
                <div className="text-muted-ink text-sm">{t("transaction")}</div>
              </button>
            ))}

            {readiness && (
              <section className="mt-4" aria-labelledby="readiness-title">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 id="readiness-title" className="font-semibold">
                    {t("readinessTitle")}
                  </h3>
                  <span className="text-muted-ink text-sm tabular-nums">
                    {t("readinessCounter", {
                      satisfied: readiness.requiredSatisfied,
                      total: readiness.requiredTotal,
                    })}
                  </span>
                </div>
                <p className="text-muted-ink mt-1 text-sm">
                  {t("readinessBody")}
                </p>
                <ul className="border-border mt-3 max-h-64 overflow-y-auto rounded border">
                  {readiness.fields.map(({ field, fact, status }) => (
                    <li
                      key={field.id}
                      className="border-border flex items-center justify-between gap-3 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <span className="flex items-center gap-2">
                        {tf(factLabelKey(field.labelKey))}
                        {!field.required && (
                          <span className="text-muted-ink text-xs">
                            {t("readinessOptional")}
                          </span>
                        )}
                      </span>
                      {status === "satisfied" ? (
                        <span className="text-muted-ink max-w-[45%] truncate text-right">
                          {String(fact?.value ?? "")}
                        </span>
                      ) : (
                        <Link
                          className="shrink-0"
                          href={`/matters/${matterId}/facts`}
                        >
                          <StatusBadge
                            status={status === "missing" ? "blocked" : status}
                          />
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {blocked && readiness && (
              <div className="border-red bg-red-bg mt-4 border-l-2 p-4">
                <div className="text-red flex items-center gap-2 font-semibold">
                  <ShieldAlert className="size-5" strokeWidth={1.5} />
                  {t("blockedTitle")}
                </div>
                <p className="mt-1 text-sm">{t("blockedBody")}</p>
                <div className="text-red mt-2 text-xs">
                  {t("missingFacts")}:{" "}
                  {readiness.outstanding
                    .map((entry) => tf(factLabelKey(entry.field.labelKey)))
                    .join(" · ")}
                </div>
              </div>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <Button onClick={() => setOpen(false)}>{t("cancel")}</Button>
              <Button
                variant="primary"
                onClick={generate}
                disabled={!readiness?.canGenerate}
                title={
                  readiness?.canGenerate ? undefined : t("readinessGateHint")
                }
              >
                {t("generate")}
              </Button>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
