"use client";

import { FileSearch, Link2, Plus, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useDemoStore } from "@/lib/store";
import type { VerifiedFact } from "@/types";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

type FactKey =
  | "deedNumber"
  | "transferor"
  | "transferee"
  | "extent"
  | "assessmentNumber";
type Filter = "all" | "unreviewed" | "low" | "conflict" | "missing";

export function FactsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("facts");
  const allFacts = useDemoStore((state) => state.facts);
  const verifyFact = useDemoStore((state) => state.verifyFact);
  const correctFact = useDemoStore((state) => state.correctFact);
  const addManualFact = useDemoStore((state) => state.addManualFact);
  const facts = allFacts.filter((fact) => fact.matterId === matterId);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState(
    facts.find((fact) => fact.verificationState === "conflict")?.id ??
      facts[0]?.id,
  );
  const [editId, setEditId] = useState<string>();
  const [editValue, setEditValue] = useState("");
  const [editReason, setEditReason] = useState("");
  const [manual, setManual] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const selected = facts.find((fact) => fact.id === selectedId) ?? facts[0];
  const visible = facts.filter(
    (fact) =>
      filter === "all" ||
      (filter === "unreviewed" && fact.verificationState === "unreviewed") ||
      (filter === "low" && fact.confidence < 0.8) ||
      (filter === "conflict" && fact.verificationState === "conflict") ||
      (filter === "missing" && fact.verificationState === "blocked"),
  );
  const label = (fact: VerifiedFact) =>
    t(fact.labelKey.split(".").at(-1) as FactKey, { fallback: fact.key });
  const beginCorrection = (fact: VerifiedFact) => {
    setEditId(fact.id);
    setEditValue(String(fact.value ?? ""));
    setEditReason("");
  };
  const saveCorrection = () => {
    if (!editId || !editReason.trim()) return;
    correctFact(editId, editValue, editReason);
    setEditId(undefined);
    setSelectedId(editId);
  };
  const applyConflict = (fact: VerifiedFact, value: VerifiedFact["value"]) => {
    correctFact(fact.id, value, t("conflictTitle"));
    setSelectedId(fact.id);
  };
  const filters: Array<{ key: Filter; label: string }> = [
    { key: "all", label: t("all") },
    { key: "unreviewed", label: t("unreviewedFilter") },
    { key: "low", label: t("lowConfidence") },
    { key: "conflict", label: t("conflicting") },
    { key: "missing", label: t("missing") },
  ];
  return (
    <AppShell matterId={matterId}>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          <Button onClick={() => setManual(true)}>
            <Plus className="size-4" strokeWidth={1.5} />
            {t("addManual")}
          </Button>
        }
      />
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="p-6">
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="border-border-strong bg-surface flex flex-wrap rounded border p-1"
            role="group"
            aria-label={t("title")}
          >
            {filters.map((item) => (
              <button
                key={item.key}
                aria-pressed={filter === item.key}
                className={`min-h-9 rounded px-3 text-sm ${filter === item.key ? "bg-selected-bg text-forest font-semibold" : "hover:bg-hover-bg"}`}
                onClick={() => setFilter(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <Button
            className="ml-auto"
            onClick={() => {
              facts
                .filter((fact) => fact.verificationState === "unreviewed")
                .forEach((fact) => verifyFact(fact.id));
              setAnnouncement(t("batchComplete"));
            }}
          >
            <ShieldCheck className="size-4" strokeWidth={1.5} />
            {t("verifySection")}
          </Button>
          <Button onClick={() => setAnnouncement(t("duplicateReady"))}>
            <Link2 className="size-4" strokeWidth={1.5} />
            {t("linkDuplicates")}
          </Button>
        </div>
        <section className="border-border-strong bg-surface mt-4 overflow-hidden rounded border">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse text-left">
              <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
                <tr className="border-border h-10 border-b">
                  <th className="px-3">{t("fact")}</th>
                  <th className="px-3">{t("value")}</th>
                  <th className="px-3">{t("source")}</th>
                  <th className="px-3">{t("pinpoint")}</th>
                  <th className="px-3">{t("confidence")}</th>
                  <th className="px-3">{t("reviewer")}</th>
                  <th className="px-3">{t("status")}</th>
                  <th className="px-3">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((fact) => (
                  <tr
                    key={fact.id}
                    className={`border-border h-11 border-b last:border-b-0 ${selected?.id === fact.id ? "border-l-forest bg-selected-bg border-l-2" : "hover:bg-hover-bg"}`}
                  >
                    <td className="px-3 font-medium">
                      <button
                        className="hover:text-teal text-left"
                        onClick={() => setSelectedId(fact.id)}
                      >
                        {label(fact)}
                      </button>
                    </td>
                    <td className="max-w-56 truncate px-3">
                      {String(fact.value ?? "—")}
                    </td>
                    <td className="max-w-44 truncate px-3 text-sm">
                      {fact.evidence?.documentId ?? t("unknownSource")}
                    </td>
                    <td className="text-teal px-3 text-sm">
                      {fact.evidence
                        ? t("pagePinpoint", { page: fact.evidence.page })
                        : "—"}
                    </td>
                    <td className="px-3 tabular-nums">
                      {Math.round(fact.confidence * 100)}%
                    </td>
                    <td className="px-3 text-sm">
                      {fact.reviewerId
                        ? t("syntheticReviewer")
                        : t("notReviewed")}
                    </td>
                    <td className="px-3">
                      <StatusBadge status={fact.verificationState} />
                    </td>
                    <td className="px-3">
                      <div className="flex items-center gap-1">
                        {fact.verificationState === "unreviewed" && (
                          <Button
                            className="min-h-9 px-2 py-1 text-xs"
                            variant="primary"
                            onClick={() => verifyFact(fact.id)}
                          >
                            {t("verify")}
                          </Button>
                        )}
                        <button
                          aria-label={t("openEvidence", { fact: label(fact) })}
                          title={t("openEvidence", { fact: label(fact) })}
                          className="hover:bg-active-bg grid size-9 place-items-center rounded"
                          onClick={() => setSelectedId(fact.id)}
                        >
                          <FileSearch className="size-4" strokeWidth={1.5} />
                        </button>
                        {fact.verificationState === "conflict" ? (
                          <Button
                            className="min-h-9 px-2 py-1 text-xs"
                            onClick={() => setSelectedId(fact.id)}
                          >
                            {t("compare")}
                          </Button>
                        ) : fact.verificationState === "blocked" ? (
                          <Button
                            className="min-h-9 px-2 py-1 text-xs"
                            onClick={() => setManual(true)}
                          >
                            {t("resolve")}
                          </Button>
                        ) : (
                          <Button
                            className="min-h-9 px-2 py-1 text-xs"
                            onClick={() => beginCorrection(fact)}
                          >
                            {t("correct")}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        {selected && (
          <section className="border-border-strong bg-surface mt-6 grid overflow-hidden rounded border lg:grid-cols-[1fr_360px]">
            <div className="bg-canvas min-h-80 p-6">
              <h2 className="text-xl font-semibold">{t("evidenceTitle")}</h2>
              <div className="border-border-strong bg-surface mt-4 min-h-60 border p-8">
                <div className="font-heading text-2xl font-semibold">
                  {selected.evidence
                    ? t("syntheticPage", { page: selected.evidence.page })
                    : t("noEvidence")}
                </div>
                {selected.evidence && (
                  <div className="border-teal bg-teal-bg mt-8 border-l-2 p-4">
                    <div className="text-teal text-xs font-semibold uppercase">
                      {t("highlight")}
                    </div>
                    <p className="mt-1">{selected.evidence.snippet}</p>
                  </div>
                )}
              </div>
            </div>
            <aside className="border-border border-t p-4 lg:border-l lg:border-t-0">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-xl font-semibold">{label(selected)}</h2>
                <StatusBadge status={selected.verificationState} />
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="text-muted-ink">{t("extractedValue")}</dt>
                  <dd className="font-medium">
                    {String(selected.extractedValue ?? "—")}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-ink">{t("correctedValue")}</dt>
                  <dd className="font-medium">
                    {String(selected.value ?? "—")}
                  </dd>
                </div>
              </dl>
              {selected.changes.length > 0 && (
                <div className="mt-5">
                  <h3 className="font-semibold">{t("history")}</h3>
                  {selected.changes.map((change) => (
                    <div
                      key={change.id}
                      className="border-border mt-2 rounded border p-3 text-sm"
                    >
                      <div>
                        <span className="text-red line-through">
                          {String(change.before)}
                        </span>{" "}
                        →{" "}
                        <span className="text-teal">
                          {String(change.after)}
                        </span>
                      </div>
                      <div className="text-muted-ink mt-1 text-xs">
                        {change.reason}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {selected.verificationState === "conflict" && (
                <ConflictComparison
                  fact={selected}
                  onUse={(value) => applyConflict(selected, value)}
                />
              )}
            </aside>
          </section>
        )}
        {editId && (
          <div
            className="bg-ink/25 fixed inset-0 z-40 grid place-items-center p-4"
            role="presentation"
          >
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="correction-title"
              className="rounded-dialog border-border-strong bg-surface shadow-dialog w-full max-w-lg border p-5"
            >
              <h2 id="correction-title" className="text-2xl font-semibold">
                {t("correctionTitle")}
              </h2>
              <label className="mt-4 block font-medium">
                {t("correctedValue")}
                <input
                  className="border-border-strong mt-1 h-10 w-full rounded border px-3"
                  value={editValue}
                  onChange={(event) => setEditValue(event.target.value)}
                />
              </label>
              <label className="mt-3 block font-medium">
                {t("correctionReason")}
                <textarea
                  className="border-border-strong mt-1 min-h-24 w-full rounded border p-3"
                  value={editReason}
                  onChange={(event) => setEditReason(event.target.value)}
                />
              </label>
              <div className="mt-4 flex justify-end gap-2">
                <Button onClick={() => setEditId(undefined)}>
                  {t("cancel")}
                </Button>
                <Button
                  variant="primary"
                  disabled={!editReason.trim()}
                  onClick={saveCorrection}
                >
                  {t("saveCorrection")}
                </Button>
              </div>
            </section>
          </div>
        )}
        {manual && (
          <ManualFactDialog
            onClose={() => setManual(false)}
            onAdd={(value, reason) => {
              const id = addManualFact("facts.manualValue", value, reason);
              setSelectedId(id);
              setManual(false);
              setAnnouncement(t("manualAdded"));
            }}
          />
        )}
      </div>
    </AppShell>
  );
}

function ConflictComparison({
  fact,
  onUse,
}: {
  fact: VerifiedFact;
  onUse: (value: VerifiedFact["value"]) => void;
}) {
  const t = useTranslations("facts");
  return (
    <div className="mt-5">
      <h3 className="text-amber-text font-semibold">{t("conflictTitle")}</h3>
      <div className="mt-2 space-y-2">
        {fact.conflicts?.map((candidate, index) => (
          <div
            key={`${candidate.evidence.documentId}-${index}`}
            className="border-amber bg-amber-bg rounded border p-3"
          >
            <div className="text-amber-text text-xs">
              {t("candidate", { number: index + 1 })} ·{" "}
              {t("pagePinpoint", { page: candidate.evidence.page })}
            </div>
            <div className="mt-1 font-medium">{String(candidate.value)}</div>
            <div className="mt-1 text-xs text-ink">
              {candidate.evidence.snippet}
            </div>
            <Button
              className="mt-2 min-h-9"
              onClick={() => onUse(candidate.value)}
            >
              {t("useValue")}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function ManualFactDialog({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (value: string, reason: string) => void;
}) {
  const t = useTranslations("facts");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  return (
    <div
      className="bg-ink/25 fixed inset-0 z-40 grid place-items-center p-4"
      role="presentation"
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="manual-title"
        className="rounded-dialog border-border-strong bg-surface shadow-dialog w-full max-w-lg border p-5"
      >
        <h2 id="manual-title" className="text-2xl font-semibold">
          {t("addManual")}
        </h2>
        <label className="mt-4 block font-medium">
          {t("manualValue")}
          <input
            className="border-border-strong mt-1 h-10 w-full rounded border px-3"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <label className="mt-3 block font-medium">
          {t("manualReason")}
          <textarea
            className="border-border-strong mt-1 min-h-24 w-full rounded border p-3"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            disabled={!value.trim() || !reason.trim()}
            onClick={() => onAdd(value, reason)}
          >
            {t("add")}
          </Button>
        </div>
      </section>
    </div>
  );
}
