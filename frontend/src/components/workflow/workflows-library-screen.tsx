"use client";

import {
  BookOpenCheck,
  FileText,
  LockKeyhole,
  Play,
  ScrollText,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { questionSets, templates, workflows } from "@/lib/mocks";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

type Tab = "functions" | "templates" | "questionSets" | "examples";

export function WorkflowsLibraryScreen() {
  const t = useTranslations("workflow");
  const [tab, setTab] = useState<Tab>("functions");
  const tabs: Tab[] = ["functions", "templates", "questionSets", "examples"];
  return (
    <AppShell>
      <PageHeader
        title={t("libraryTitle")}
        description={t("libraryDescription")}
      />
      <div className="p-6">
        <div className="border-border flex flex-wrap gap-3 border-b pb-4">
          <label className="text-muted-ink text-sm">
            {t("regimeFilter")}
            <select className="border-border-strong bg-surface text-ink ml-2 h-10 rounded border px-3">
              <option>{t("all")}</option>
              <option>{t("rta")}</option>
            </select>
          </label>
          <label className="text-muted-ink text-sm">
            {t("transactionFilter")}
            <select className="border-border-strong bg-surface text-ink ml-2 h-10 rounded border px-3">
              <option>{t("all")}</option>
              <option>{t("transfer")}</option>
            </select>
          </label>
          <label className="text-muted-ink text-sm">
            {t("approvalFilter")}
            <select className="border-border-strong bg-surface text-ink ml-2 h-10 rounded border px-3">
              <option>{t("approved")}</option>
            </select>
          </label>
        </div>
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
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {tab === "functions" &&
            workflows.map((workflow) => (
              <LibraryItem
                key={workflow.id}
                icon={<BookOpenCheck />}
                title={t("examinationTitle")}
                meta={`${t("rta")} · ${t("bilingual")} · ${t("version", { version: workflow.version })}`}
                href={`/workflows/${workflow.id}`}
                action={t("run")}
              />
            ))}
          {tab === "templates" &&
            templates.map((template) => (
              <LibraryItem
                key={template.id}
                icon={<FileText />}
                title={t("form8Template")}
                meta={`${t("rta")} · ${t("transfer")} · ${t("approved")}`}
              />
            ))}
          {tab === "questionSets" &&
            questionSets.map((set) => (
              <LibraryItem
                key={set.id}
                icon={<ScrollText />}
                title={t("questionBank")}
                meta={t("approved")}
              />
            ))}
          {tab === "examples" && (
            <LibraryItem
              icon={<Play />}
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
          <Play className="size-4" />
        </span>
      )}
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
