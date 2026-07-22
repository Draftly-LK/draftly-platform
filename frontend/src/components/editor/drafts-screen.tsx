"use client";

import { ArrowRight, FilePlus2, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { templates } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";

const stateKeys = {
  working: "working",
  "in-review": "inReview",
  approved: "approved",
  exported: "exported",
} as const;

export function DraftsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("draft");
  const allDrafts = useDemoStore((state) => state.drafts);
  const facts = useDemoStore((state) => state.facts);
  const createDraft = useDemoStore((state) => state.createDraft);
  const drafts = allDrafts.filter((draft) => draft.matterId === matterId);
  const [open, setOpen] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const eligible = facts.filter(
    (fact) =>
      fact.matterId === matterId &&
      ["verified", "corrected"].includes(fact.verificationState),
  );
  const unready = facts.filter(
    (fact) =>
      fact.matterId === matterId &&
      !["verified", "corrected"].includes(fact.verificationState),
  );
  const generate = () => {
    const id = createDraft(matterId, "template-form8-001");
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
            {templates
              .filter((template) => template.approvalState === "approved")
              .map((template) => (
                <div
                  key={template.id}
                  className="border-forest bg-selected-bg mt-4 rounded border p-4"
                >
                  <div className="text-forest text-xs font-semibold uppercase">
                    {t("approvedTemplate")}
                  </div>
                  <div className="font-heading mt-1 text-xl font-semibold">
                    {t("form8Name")}
                  </div>
                  <div className="text-muted-ink text-sm">
                    {t("transaction")}
                  </div>
                </div>
              ))}
            {blocked ? (
              <div className="border-red bg-red-bg mt-4 border-l-2 p-4">
                <div className="text-red flex items-center gap-2 font-semibold">
                  <ShieldAlert className="size-5" strokeWidth={1.5} />
                  {t("blockedTitle")}
                </div>
                <p className="mt-1 text-sm">{t("blockedBody")}</p>
                <div className="text-red mt-2 text-xs">
                  {t("missingFacts")}:{" "}
                  {unready.map((fact) => fact.key).join(" · ")}
                </div>
              </div>
            ) : (
              <div className="border-forest bg-soft-green mt-4 border-l-2 p-3 text-sm">
                <strong>{t("readyFacts")}:</strong>{" "}
                {eligible.map((fact) => fact.key).join(" · ")}
              </div>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <Button onClick={() => setOpen(false)}>{t("cancel")}</Button>
              <Button variant="primary" onClick={generate}>
                {t("generate")}
              </Button>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
