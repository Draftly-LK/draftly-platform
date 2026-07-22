"use client";

import { Check, Download, GitCompare, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useDemoStore } from "@/lib/store";
import type {
  EditorDocument,
  EditorFactChipNode,
  EditorHeadingNode,
  EditorLockedNode,
  EditorParagraphNode,
  EditorTextNode,
} from "@/types";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { EditorShell } from "./editor-shell";

export function DraftEditorScreen({
  matterId,
  draftId,
}: {
  matterId: string;
  draftId: string;
}) {
  const t = useTranslations("draft");
  const allDrafts = useDemoStore((state) => state.drafts);
  const facts = useDemoStore((state) => state.facts);
  const saveDraftVersion = useDemoStore((state) => state.saveDraftVersion);
  const restoreDraftVersion = useDemoStore(
    (state) => state.restoreDraftVersion,
  );
  const approveDraft = useDemoStore((state) => state.approveDraft);
  const exportDraft = useDemoStore((state) => state.exportDraft);
  const draft = allDrafts.find((item) => item.id === draftId);
  const [selectedVersionId, setSelectedVersionId] = useState(
    draft?.activeVersionId,
  );
  const [compare, setCompare] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  useEffect(() => {
    if (draft?.activeVersionId && !selectedVersionId)
      setSelectedVersionId(draft.activeVersionId);
  }, [draft?.activeVersionId, selectedVersionId]);
  if (!draft) return null;
  const selected =
    draft.versions.find((version) => version.id === selectedVersionId) ??
    draft.versions.at(-1);
  const current =
    draft.versions.find((version) => version.id === draft.activeVersionId) ??
    draft.versions.at(-1);
  const previous = draft.versions.at(-2);
  if (!selected || !current) return null;
  const editable = selected.id === draft.activeVersionId;
  const canExport =
    draft.approvalState === "approved" || draft.approvalState === "exported";
  const save = (document: EditorDocument) => {
    saveDraftVersion(draft.id, document);
    const activeVersionId = useDemoStore
      .getState()
      .drafts.find((item) => item.id === draft.id)?.activeVersionId;
    setSelectedVersionId(activeVersionId);
    setAnnouncement(t("saved"));
  };
  const restore = () => {
    restoreDraftVersion(draft.id, selected.id);
    setCompare(false);
    setAnnouncement(t("restored"));
  };
  const approve = () => {
    approveDraft(draft.id);
    setAnnouncement(t("approvedNotice"));
  };
  const exportFile = (format: "docx" | "pdf") => {
    exportDraft(draft.id, format);
    setAnnouncement(t("exportStub"));
  };
  return (
    <AppShell matterId={matterId}>
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <header
        data-no-print
        className="border-border bg-surface flex flex-wrap items-center gap-2 border-b px-5 py-3"
      >
        <div className="w-full min-w-0 min-[1200px]:w-auto min-[1200px]:flex-1">
          <h1 className="text-2xl font-semibold">{t("editorTitle")}</h1>
          <div className="text-muted-ink mt-1 text-xs">
            {t("versionPill", { number: selected.number, hash: selected.hash })}
          </div>
        </div>
        <label className="sr-only" htmlFor="version-select">
          {t("version")}
        </label>
        <select
          id="version-select"
          className="border-border-strong bg-surface h-10 rounded border px-3"
          value={selected.id}
          onChange={(event) => setSelectedVersionId(event.target.value)}
        >
          {draft.versions.map((version) => (
            <option key={version.id} value={version.id}>
              {t("versionPill", { number: version.number, hash: version.hash })}
            </option>
          ))}
        </select>
        <Button onClick={() => setCompare((value) => !value)}>
          <GitCompare className="size-4" strokeWidth={1.5} />
          {compare ? t("closeCompare") : t("compare")}
        </Button>
        {!editable && (
          <Button onClick={restore}>
            <RotateCcw className="size-4" strokeWidth={1.5} />
            {t("restore")}
          </Button>
        )}
        <Button
          variant="primary"
          disabled={
            !editable ||
            draft.approvalState === "approved" ||
            draft.approvalState === "exported"
          }
          onClick={approve}
        >
          <Check className="size-4" strokeWidth={1.5} />
          {t("approve")}
        </Button>
        <Button
          disabled={!canExport}
          onClick={() => exportFile("docx")}
          title={!canExport ? t("exportGate") : t("exportDocx")}
        >
          <Download className="size-4" strokeWidth={1.5} />
          {t("exportDocx")}
        </Button>
        <Button
          disabled={!canExport}
          onClick={() => exportFile("pdf")}
          title={!canExport ? t("exportGate") : t("exportPdf")}
        >
          <Download className="size-4" strokeWidth={1.5} />
          {t("exportPdf")}
        </Button>
      </header>
      {!editable && (
        <div className="border-amber bg-amber-bg text-amber-text border-b px-5 py-3">
          {t("readOnlyBanner")}
        </div>
      )}
      {compare && previous ? (
        <div className="bg-canvas grid gap-4 p-6 md:grid-cols-2">
          <VersionPanel
            title={t("previousVersion")}
            text={documentText(previous.document, facts)}
          />
          <VersionPanel
            title={t("currentVersion")}
            text={documentText(current.document, facts)}
          />
        </div>
      ) : (
        <EditorShell
          key={selected.id}
          version={selected}
          facts={facts.filter((fact) => fact.matterId === matterId)}
          editable={editable}
          onSave={save}
        />
      )}
    </AppShell>
  );
}

function VersionPanel({ title, text }: { title: string; text: string }) {
  return (
    <section className="border-border-strong bg-surface min-h-96 rounded border p-6">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="font-heading mt-4 whitespace-pre-wrap text-lg leading-8">
        {text}
      </div>
    </section>
  );
}

type EditorNode =
  | EditorParagraphNode
  | EditorHeadingNode
  | EditorLockedNode
  | EditorTextNode
  | EditorFactChipNode;
function documentText(
  document: EditorDocument,
  facts: ReturnType<typeof useDemoStore.getState>["facts"],
): string {
  const read = (node: EditorNode): string => {
    if (node.type === "text") return node.text;
    if (node.type === "factChip")
      return `[${String(facts.find((fact) => fact.id === node.attrs.fact_id)?.value ?? node.attrs.fact_id)}]`;
    return (
      node.content?.map((child) => read(child as EditorNode)).join("") ?? ""
    );
  };
  return document.content.map((node) => read(node)).join("\n\n");
}
