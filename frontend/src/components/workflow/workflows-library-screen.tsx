"use client";

import {
  BookOpenCheck,
  CircleDashed,
  FileText,
  FlaskConical,
  LockKeyhole,
  Play,
  ScrollText,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useMemo, useState } from "react";
import { questionSets, templates, workflows } from "@/lib/mocks";
import {
  availableRtaWorkflowCount,
  rtaWorkflowsByFamily,
  type RtaWorkflow,
} from "@/lib/rta/workflow-catalogue";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

type Tab = "functions" | "templates" | "questionSets" | "examples";

const ALL_FAMILIES = "all" as const;

export function WorkflowsLibraryScreen() {
  const t = useTranslations("workflow");
  /** Family and instrument names are authored in the rule pack, so they resolve
   *  from the message root rather than the `workflow` namespace. */
  const tRoot = useTranslations();
  const [tab, setTab] = useState<Tab>("functions");
  const [familyFilter, setFamilyFilter] = useState<string>(ALL_FAMILIES);
  const [availableOnly, setAvailableOnly] = useState(false);
  const tabs: Tab[] = ["functions", "templates", "questionSets", "examples"];

  const groups = useMemo(() => rtaWorkflowsByFamily(), []);
  const totalCount = useMemo(
    () => groups.reduce((sum, group) => sum + group.workflows.length, 0),
    [groups],
  );
  const availableCount = useMemo(() => availableRtaWorkflowCount(), []);

  const visibleGroups = groups
    .filter((group) => familyFilter === ALL_FAMILIES || group.family.id === familyFilter)
    .map((group) => ({
      ...group,
      workflows: availableOnly
        ? group.workflows.filter((workflow) => workflow.available)
        : group.workflows,
    }))
    .filter((group) => group.workflows.length > 0);

  return (
    <AppShell>
      <PageHeader
        title={t("libraryTitle")}
        description={t("libraryDescription")}
      />
      <div className="p-6">
        {tab === "functions" && (
          <div className="border-border flex flex-wrap items-end gap-4 border-b pb-4">
            <label className="text-muted-ink text-sm">
              {t("familyFilter")}
              <select
                className="border-border-strong bg-surface text-ink ml-2 h-10 rounded border px-3"
                value={familyFilter}
                onChange={(event) => setFamilyFilter(event.target.value)}
              >
                <option value={ALL_FAMILIES}>{t("all")}</option>
                {groups.map((group) => (
                  <option key={group.family.id} value={group.family.id}>
                    {tRoot(group.family.labelKey)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-muted-ink inline-flex min-h-10 items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="accent-forest size-4"
                checked={availableOnly}
                onChange={(event) => setAvailableOnly(event.target.checked)}
              />
              {t("availableOnly")}
            </label>
          </div>
        )}
        <div
          className="border-border mt-4 flex overflow-x-auto border-b"
          role="tablist"
          aria-label={t("libraryTitle")}
        >
          {tabs.map((item) => (
            <button
              key={item}
              role="tab"
              aria-selected={tab === item}
              className={`min-h-11 shrink-0 border-b-2 px-4 ${tab === item ? "border-forest text-forest font-semibold" : "text-muted-ink border-transparent"}`}
              onClick={() => setTab(item)}
            >
              {t(item)}
            </button>
          ))}
        </div>

        {tab === "functions" && (
          <>
            <h2 className="font-heading mt-6 text-xl font-semibold">
              {t("runnableTitle")}
            </h2>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {workflows.map((workflow) => (
                <LibraryItem
                  key={workflow.id}
                  icon={<BookOpenCheck strokeWidth={1.5} />}
                  title={t("examinationTitle")}
                  meta={`${t("rta")} · ${t("bilingual")} · ${t("version", { version: workflow.version })}`}
                  href={`/workflows/${workflow.id}`}
                  action={t("run")}
                />
              ))}
            </div>

            <h2 className="font-heading mt-8 text-xl font-semibold">
              {t("catalogueTitle")}
            </h2>
            <p className="text-muted-ink mt-1 max-w-3xl text-sm">
              {t("catalogueSubtitle", { total: totalCount, available: availableCount })}
            </p>
            {visibleGroups.length === 0 ? (
              <p className="text-muted-ink mt-6 text-sm">{t("emptyFilter")}</p>
            ) : (
              visibleGroups.map((group) => (
                <section key={group.family.id} className="mt-6">
                  <h3 className="text-muted-ink text-xs font-semibold uppercase">
                    {tRoot(group.family.labelKey)}
                  </h3>
                  <div className="border-border bg-surface divide-border mt-2 divide-y rounded border">
                    {group.workflows.map((workflow) => (
                      <WorkflowRow key={workflow.subtype.id} workflow={workflow} />
                    ))}
                  </div>
                </section>
              ))
            )}
          </>
        )}

        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {tab === "templates" &&
            templates.map((template) => (
              <LibraryItem
                key={template.id}
                icon={<FileText strokeWidth={1.5} />}
                title={t("form8Template")}
                meta={`${t("rta")} · ${t("transfer")} · ${t("approved")}`}
              />
            ))}
          {tab === "questionSets" &&
            questionSets.map((set) => (
              <LibraryItem
                key={set.id}
                icon={<ScrollText strokeWidth={1.5} />}
                title={t("questionBank")}
                meta={t("approved")}
              />
            ))}
          {tab === "examples" && (
            <LibraryItem
              icon={<Play strokeWidth={1.5} />}
              title={t("exampleTitle")}
              meta={t("exampleBody")}
            />
          )}
        </div>
        <div className="border-border text-muted-ink mt-6 flex items-center gap-2 border-y py-4 text-sm">
          <LockKeyhole className="size-4" strokeWidth={1.5} />
          {t("maintainerOnly")}
        </div>
      </div>
    </AppShell>
  );
}

function WorkflowRow({ workflow }: { workflow: RtaWorkflow }) {
  const t = useTranslations("workflow");
  const tRoot = useTranslations();
  const { subtype, available } = workflow;
  const form =
    subtype.gazetteFormNumber === null
      ? t("noGazetteForm")
      : t("gazetteForm", { number: subtype.gazetteFormNumber });
  // Status is icon + text, never colour alone.
  const TierIcon = available ? FlaskConical : CircleDashed;

  return (
    <div className="hover:bg-hover-bg grid min-h-14 grid-cols-[1fr_auto] items-center gap-4 px-4 py-2">
      <div className="min-w-0">
        <div className="font-medium">{tRoot(subtype.labelKey)}</div>
        <div className="text-muted-ink text-xs">
          {form} · {t(`examination.${subtype.examinationLevel}`)}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="border-border-strong inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium">
          <TierIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
          {t(`tier.${subtype.releaseTier}`)}
        </span>
        {available ? (
          <Link href="/new" className="text-teal text-sm font-medium hover:underline">
            {t("startMatter")}
          </Link>
        ) : (
          <span className="text-muted-ink text-sm">{t("notPrepared")}</span>
        )}
      </div>
    </div>
  );
}

function LibraryItem({
  icon,
  title,
  meta,
  href,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  meta: string;
  href?: string;
  action?: string;
}) {
  const body = (
    <div className="border-border-strong bg-surface hover:bg-hover-bg flex min-h-24 items-center gap-4 rounded border p-4">
      <span className="bg-selected-bg text-forest grid size-10 place-items-center rounded [&_svg]:size-5 [&_svg]:stroke-[1.5]">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="font-heading block text-xl font-semibold">
          {title}
        </span>
        <span className="text-muted-ink mt-1 block text-sm">{meta}</span>
      </span>
      {action && (
        <span className="text-teal inline-flex items-center gap-2 font-medium">
          {action}
          <Play className="size-4" strokeWidth={1.5} />
        </span>
      )}
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
