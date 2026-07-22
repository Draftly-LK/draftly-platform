"use client";

import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Headphones,
  MessageSquareText,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useDemoStore } from "@/lib/store";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { StatusBadge } from "@/components/ui/status-badge";

type StepTitleKey =
  | "identityTitle"
  | "titleTitle"
  | "encumbranceTitle"
  | "decisionTitle";
type StepObjectiveKey =
  | "identityObjective"
  | "titleObjective"
  | "encumbranceObjective"
  | "decisionObjective";
type RuleKey = "identityRule" | "titleRule" | "encumbranceRule";

export function WorkflowScreen({
  matterId,
  standalone = false,
}: {
  matterId: string;
  standalone?: boolean;
}) {
  const t = useTranslations("workflow");
  const workflows = useDemoStore((state) => state.workflows);
  const completeStep = useDemoStore((state) => state.completeStep);
  const workflow = workflows[0];
  const [selectedId, setSelectedId] = useState(
    workflow?.steps.find((step) => step.state === "in-progress")?.id ??
      workflow?.steps[0]?.id,
  );
  const [note, setNote] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [announcement, setAnnouncement] = useState("");
  if (!workflow) return null;
  const selected =
    workflow.steps.find((step) => step.id === selectedId) ?? workflow.steps[0];
  if (!selected) return null;
  const selectedIndex = workflow.steps.findIndex(
    (step) => step.id === selected.id,
  );
  const blocked = selected.state === "blocked" && selected.mandatory;
  const finish = () => {
    if (blocked && !overrideReason.trim()) return;
    completeStep(
      workflow.id,
      selected.id,
      note,
      blocked ? overrideReason : undefined,
    );
    setAnnouncement(blocked ? t("overrideRecorded") : t("completed"));
  };
  const content = (
    <>
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div
        className={`grid min-h-[calc(100vh-166px)] lg:grid-cols-[250px_minmax(0,1fr)] ${assistantOpen ? "min-[1280px]:grid-cols-[250px_minmax(420px,1fr)_360px]" : ""}`}
      >
        <aside className="border-border bg-canvas border-b p-3 lg:border-b-0 lg:border-r">
          <h2 className="px-2 text-sm font-semibold">{t("steps")}</h2>
          <div className="mt-2 space-y-1">
            {workflow.steps.map((step) => (
              <button
                key={step.id}
                className={`flex min-h-14 w-full items-center gap-3 rounded border-l-2 px-3 text-left ${selected.id === step.id ? "border-forest bg-selected-bg" : "hover:bg-hover-bg border-transparent"}`}
                onClick={() => {
                  setSelectedId(step.id);
                  setNote(step.note ?? "");
                  setOverrideReason(step.overrideReason ?? "");
                }}
              >
                <span className="border-border-strong grid size-7 shrink-0 place-items-center rounded-full border text-xs tabular-nums">
                  {step.order}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">
                    {t(step.titleKey.split(".").at(-1) as StepTitleKey)}
                  </span>
                  <StatusBadge status={step.state} className="mt-1" />
                </span>
              </button>
            ))}
          </div>
        </aside>
        <main className="bg-surface min-w-0">
          <header className="border-border flex items-start gap-3 border-b px-6 py-5">
            <div className="min-w-0 flex-1">
              <div className="text-muted-ink text-xs font-semibold uppercase">
                {t("stepCount", {
                  current: selected.order,
                  total: workflow.steps.length,
                })}
              </div>
              <h1 className="mt-1 text-3xl font-semibold">
                {t(selected.titleKey.split(".").at(-1) as StepTitleKey)}
              </h1>
            </div>
            <IconButton label={t("listen")}>
              <Headphones className="size-5" strokeWidth={1.5} />
            </IconButton>
            <IconButton
              label={
                assistantOpen ? t("collapseAssistant") : t("showAssistant")
              }
              onClick={() => setAssistantOpen((value) => !value)}
            >
              {assistantOpen ? (
                <PanelRightClose className="size-5" strokeWidth={1.5} />
              ) : (
                <PanelRightOpen className="size-5" strokeWidth={1.5} />
              )}
            </IconButton>
          </header>
          <div className="mx-auto max-w-3xl space-y-6 p-6">
            <Section title={t("objective")}>
              <p>
                {t(selected.objectiveKey.split(".").at(-1) as StepObjectiveKey)}
              </p>
            </Section>
            <Section title={t("requiredInputs")}>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="border-border-strong rounded border p-3">
                  <div className="font-medium">
                    {t("factsRequired", {
                      count: selected.requiredFactIds.length,
                    })}
                  </div>
                  <div className="text-muted-ink mt-1 text-sm">
                    {selected.requiredFactIds.join(" · ") || "—"}
                  </div>
                </div>
                <div className="border-border-strong rounded border p-3">
                  <div className="font-medium">
                    {t("documentsRequired", {
                      count: selected.requiredDocumentIds.length,
                    })}
                  </div>
                  <div className="text-muted-ink mt-1 text-sm">
                    {selected.requiredDocumentIds.join(" · ") || "—"}
                  </div>
                </div>
              </div>
            </Section>
            <Section title={t("authority")}>
              <div className="border-forest bg-selected-bg rounded border-l-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-heading text-xl font-semibold">
                      {selected.authority.title}
                    </div>
                    <div className="text-muted-ink text-sm">
                      {selected.authority.reference}
                    </div>
                  </div>
                  <Button>
                    <BookOpen className="size-4" strokeWidth={1.5} />
                    {t("openSource")}
                  </Button>
                </div>
                <div className="border-border mt-4 border-t pt-3">
                  <div className="text-muted-ink text-xs font-semibold uppercase">
                    {t("sourceExcerpt")}
                  </div>
                  <p className="font-heading mt-1 text-lg">
                    {selected.sourceExcerpt}
                  </p>
                </div>
              </div>
            </Section>
            <Section title={t("rules")}>
              <div className="divide-border border-border divide-y border-y">
                {selected.rules.map((rule) => (
                  <div key={rule.id} className="py-3">
                    <div className="font-medium">
                      {t(rule.labelKey.split(".").at(-1) as RuleKey)}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {rule.keywords.map((keyword) => (
                        <span
                          key={keyword}
                          className="border-border-strong rounded-full border px-2 py-1 text-xs"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
            <Section title={t("automatedChecks")}>
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={blocked ? "fail" : "pass"} />
                <StatusBadge
                  status={
                    selected.requiredDocumentIds.length > 1
                      ? "warning"
                      : "needs-review"
                  }
                />
              </div>
            </Section>
            <Section title={t("lawyerDecision")}>
              <label className="block font-medium">
                {t("note")}
                <textarea
                  className="border-border-strong mt-1 min-h-24 w-full rounded border p-3"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
              </label>
              {blocked && (
                <label className="text-red mt-3 block font-medium">
                  {t("override")}
                  <textarea
                    className="border-red text-ink mt-1 min-h-20 w-full rounded border p-3"
                    value={overrideReason}
                    onChange={(event) => setOverrideReason(event.target.value)}
                  />
                </label>
              )}
            </Section>
          </div>
          <footer className="border-border bg-surface sticky bottom-0 flex flex-wrap items-center gap-2 border-t px-6 py-3">
            <Button
              disabled={selectedIndex === 0}
              onClick={() =>
                setSelectedId(workflow.steps[selectedIndex - 1]?.id)
              }
            >
              <ChevronLeft className="size-4" />
              {t("previous")}
            </Button>
            <Button onClick={() => setAnnouncement(t("saved"))}>
              {t("save")}
            </Button>
            <Button
              className="ml-auto"
              variant="primary"
              disabled={blocked && !overrideReason.trim()}
              onClick={finish}
            >
              {t("continue")}
              <ChevronRight className="size-4" />
            </Button>
          </footer>
        </main>
        {assistantOpen && (
          <aside className="border-border bg-canvas hidden border-l p-4 min-[1280px]:block">
            <div className="flex items-center gap-2">
              <MessageSquareText
                className="text-forest size-5"
                strokeWidth={1.5}
              />
              <h2 className="text-xl font-semibold">{t("assistant")}</h2>
            </div>
            <p className="text-muted-ink mt-2 text-sm">{t("assistantBody")}</p>
            <Button className="mt-4 w-full">{t("ask")}</Button>
            <div className="border-border-strong bg-surface mt-5 rounded border p-3">
              <div className="text-muted-ink text-xs font-semibold uppercase">
                {t("authority")}
              </div>
              <div className="mt-1 font-medium">
                {selected.authority.reference}
              </div>
            </div>
          </aside>
        )}
      </div>
    </>
  );
  return standalone ? (
    <AppShell>{content}</AppShell>
  ) : (
    <AppShell matterId={matterId}>{content}</AppShell>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-2 text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}
