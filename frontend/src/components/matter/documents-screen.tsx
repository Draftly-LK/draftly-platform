"use client";

import { FileImage, History, RefreshCw, Replace, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { simulateDocumentProcessing, useDemoStore } from "@/lib/store";
import type { DocumentKind } from "@/types";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

const kindKeys: Record<
  DocumentKind,
  | "kindDeed"
  | "kindPlan"
  | "kindIdentity"
  | "kindAssessment"
  | "kindRegistry"
  | "kindAt"
  | "kindOther"
> = {
  deed: "kindDeed",
  "survey-plan": "kindPlan",
  identity: "kindIdentity",
  assessment: "kindAssessment",
  "registry-extract": "kindRegistry",
  "at-form": "kindAt",
  other: "kindOther",
};

export function DocumentsScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("documents");
  const tf = useTranslations("facts");
  const allDocuments = useDemoStore((state) => state.documents);
  const allFacts = useDemoStore((state) => state.facts);
  const addDocument = useDemoStore((state) => state.addDocument);
  const retryDocument = useDemoStore((state) => state.retryDocument);
  const replaceDocument = useDemoStore((state) => state.replaceDocument);
  const resolveCheck = useDemoStore((state) => state.resolveCheck);
  const documents = allDocuments.filter(
    (document) => document.matterId === matterId,
  );
  const facts = allFacts.filter((fact) => fact.matterId === matterId);
  const [selectedId, setSelectedId] = useState(documents[0]?.id);
  const [announcement, setAnnouncement] = useState("");
  const selected =
    documents.find((document) => document.id === selectedId) ?? documents[0];
  const upload = (file: File | undefined) => {
    if (!file) return;
    const id = addDocument(file.name, "other", matterId);
    setSelectedId(id);
    setAnnouncement(t("uploadReady", { name: file.name }));
    simulateDocumentProcessing(id);
  };
  const retry = (id: string) => {
    retryDocument(id);
    simulateDocumentProcessing(id);
  };
  const replace = (id: string) => {
    replaceDocument(id, t("replacementFileName"), t("replacementReason"));
    simulateDocumentProcessing(id);
  };
  return (
    <AppShell matterId={matterId}>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          <label className="border-forest bg-forest inline-flex min-h-10 cursor-pointer items-center gap-2 rounded border px-3 py-2 font-medium text-white">
            <Upload className="size-4" strokeWidth={1.5} />
            {t("upload")}
            <input
              className="sr-only"
              type="file"
              accept="application/pdf,image/*"
              onChange={(event) => upload(event.target.files?.[0])}
            />
          </label>
        }
      />
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="p-6">
        <section className="border-border-strong bg-surface overflow-hidden rounded border">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] border-collapse whitespace-nowrap text-left">
              <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
                <tr className="border-border h-10 border-b">
                  <th className="px-3">{t("file")}</th>
                  <th className="px-3">{t("type")}</th>
                  <th className="px-3">{t("language")}</th>
                  <th className="px-3">{t("pages")}</th>
                  <th className="px-3">{t("confidence")}</th>
                  <th className="px-3">{t("quality")}</th>
                  <th className="px-3">{t("state")}</th>
                  <th className="px-3">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr
                    key={document.id}
                    className={`border-border h-11 border-b last:border-b-0 ${selected?.id === document.id ? "border-l-forest bg-selected-bg border-l-2" : "hover:bg-hover-bg"}`}
                  >
                    <td className="max-w-60 truncate px-3 font-medium">
                      <button
                        className="hover:text-teal text-left"
                        onClick={() => setSelectedId(document.id)}
                      >
                        {document.fileName}
                      </button>
                      {document.kind === "at-form" && (
                        <span className="border-border-strong text-muted-ink ml-2 rounded-full border px-2 py-0.5 text-xs">
                          {t("unsupported")}
                        </span>
                      )}
                    </td>
                    <td className="px-3 text-sm">
                      {t(kindKeys[document.kind])}
                    </td>
                    <td className="px-3 uppercase">{document.language}</td>
                    <td className="px-3 tabular-nums">{document.pageCount}</td>
                    <td className="px-3 tabular-nums">
                      {document.extractionConfidence === undefined
                        ? "—"
                        : `${Math.round(document.extractionConfidence * 100)}%`}
                    </td>
                    <td className="px-3 text-sm">
                      {document.qualityProblems.length ? (
                        <span className="text-amber-text">
                          {t("qualityIssue", {
                            count: document.qualityProblems.length,
                          })}
                        </span>
                      ) : (
                        <span className="text-muted-ink">{t("noIssues")}</span>
                      )}
                    </td>
                    <td className="px-3">
                      <StatusBadge status={document.processingState} />
                    </td>
                    <td className="px-3">
                      <div className="flex items-center gap-1">
                        {document.processingState === "failed" && (
                          <button
                            aria-label={t("retry")}
                            title={t("retry")}
                            className="hover:bg-active-bg grid size-8 place-items-center rounded"
                            onClick={() => retry(document.id)}
                          >
                            <RefreshCw className="size-4" strokeWidth={1.5} />
                          </button>
                        )}
                        <button
                          aria-label={t("replace")}
                          title={t("replace")}
                          className="hover:bg-active-bg grid size-8 place-items-center rounded"
                          onClick={() => replace(document.id)}
                        >
                          <Replace className="size-4" strokeWidth={1.5} />
                        </button>
                        <button
                          className="border-border-strong hover:bg-hover-bg min-h-8 rounded border px-2 text-xs"
                          onClick={() => setSelectedId(document.id)}
                        >
                          {t("open")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        {selected && (
          <section
            aria-label={t("review", { name: selected.fileName })}
            className="border-border-strong bg-surface mt-6 grid overflow-hidden rounded border xl:grid-cols-[180px_minmax(320px,1fr)_340px]"
          >
            <aside className="border-border border-b p-3 xl:border-b-0 xl:border-r">
              <h2 className="text-sm font-semibold">{t("pageThumbs")}</h2>
              <div className="mt-3 flex gap-2 overflow-x-auto xl:block xl:space-y-2">
                {Array.from({ length: selected.pageCount }, (_, index) => (
                  <button
                    key={index}
                    className="border-border-strong bg-canvas hover:border-forest grid aspect-[3/4] w-20 shrink-0 place-items-center rounded border text-xs xl:w-full"
                    aria-label={t("page", { page: index + 1 })}
                  >
                    <FileImage className="size-5" strokeWidth={1.5} />
                    {t("page", { page: index + 1 })}
                  </button>
                ))}
              </div>
            </aside>
            <div className="border-border bg-canvas min-h-[360px] border-b p-6 xl:border-b-0 xl:border-r">
              <div className="border-border-strong bg-surface mx-auto flex min-h-[320px] max-w-lg flex-col border p-8">
                <div className="font-heading text-2xl font-semibold">
                  {t("evidence")}
                </div>
                <p className="text-muted-ink mt-3">{t("evidenceBody")}</p>
                <div className="border-teal bg-teal-bg mt-8 border-l-2 p-3 text-sm">
                  {facts.find(
                    (fact) => fact.evidence?.documentId === selected.id,
                  )?.evidence?.snippet ?? t("evidenceBody")}
                </div>
              </div>
            </div>
            <aside className="p-4">
              <h2 className="text-xl font-semibold">{t("extracted")}</h2>
              <div className="divide-border border-border mt-3 divide-y border-y">
                {facts
                  .filter((fact) => fact.evidence?.documentId === selected.id)
                  .map((fact) => (
                    <div key={fact.id} className="py-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">
                          {tf(
                            fact.labelKey.split(".").at(-1) as
                              | "deedNumber"
                              | "transferor"
                              | "transferee"
                              | "extent"
                              | "assessmentNumber",
                          )}
                        </span>
                        <StatusBadge status={fact.verificationState} />
                      </div>
                      <div className="mt-1 text-sm">
                        {String(fact.value ?? "—")}
                      </div>
                      <div className="text-teal mt-1 text-xs">
                        {t("source", { page: fact.evidence?.page ?? 1 })}
                      </div>
                    </div>
                  ))}
              </div>
              <details className="border-border-strong mt-4 rounded border p-3">
                <summary className="flex cursor-pointer items-center gap-2 font-medium">
                  <History className="size-4" strokeWidth={1.5} />
                  {t("versionHistory")}
                </summary>
                <div className="text-muted-ink mt-2 space-y-2 text-sm">
                  {selected.versions.map((version) => (
                    <div key={version.id}>
                      {version.fileName} ·{" "}
                      {version.reason || t("initialVersion")}
                    </div>
                  ))}
                </div>
              </details>
              {selected.processingState === "failed" && (
                <div className="mt-4 grid gap-2">
                  <Button onClick={() => retry(selected.id)}>
                    <RefreshCw className="size-4" strokeWidth={1.5} />
                    {t("retry")}
                  </Button>
                  <Button onClick={() => replace(selected.id)}>
                    <Replace className="size-4" strokeWidth={1.5} />
                    {t("replace")}
                  </Button>
                  <Button onClick={() => setAnnouncement(t("manualReady"))}>
                    {t("manual")}
                  </Button>
                </div>
              )}
            </aside>
          </section>
        )}
        <section className="border-border bg-surface mt-6 border-y px-4 py-5">
          <h2 className="text-xl font-semibold">
            {t("missingRecommendations")}
          </h2>
          <p className="text-muted-ink mt-1">{t("missingBody")}</p>
          <Button
            className="mt-3"
            onClick={() => {
              resolveCheck(
                "check-registry",
                "document-requested",
                t("requestReady"),
              );
              setAnnouncement(t("requestReady"));
            }}
          >
            {t("requestDocument")}
          </Button>
        </section>
      </div>
    </AppShell>
  );
}
