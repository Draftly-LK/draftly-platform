"use client";

import type { JSONContent } from "@tiptap/core";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Bold, Italic, Redo2, Save, Undo2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { DraftVersion, EditorDocument, VerifiedFact } from "@/types";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { FactChip, canInsertFact } from "./fact-chip";
import { LockedBlock } from "./locked-block";

export default function TiptapEditor({ version, facts, editable, onSave }: { version: DraftVersion; facts: VerifiedFact[]; editable: boolean; onSave: (document: EditorDocument) => void }) {
  const t = useTranslations("draft");
  const [revision, setRevision] = useState("");
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [StarterKit, Placeholder.configure({ placeholder: t("legalPlaceholder") }), FactChip.configure({ facts }), LockedBlock],
    content: version.document as JSONContent,
    editable,
    editorProps: { attributes: { class: "draft-prose min-h-[620px] outline-none" } },
  }, [version.id, editable]);
  const eligibleFacts = facts.filter(canInsertFact);
  const missingFacts = facts.filter((fact) => !canInsertFact(fact));
  const insert = (fact: VerifiedFact) => {
    if (!editor || !canInsertFact(fact)) return;
    editor.chain().focus().insertContent({ type: "factChip", attrs: { fact_id: fact.id, verification_state: fact.verificationState } }).run();
  };
  return <div className="grid min-h-[720px] min-[1200px]:grid-cols-[300px_minmax(0,1fr)]"><aside className="flex flex-col border-b border-border bg-canvas p-4 min-[1200px]:sticky min-[1200px]:top-0 min-[1200px]:max-h-screen min-[1200px]:border-b-0 min-[1200px]:border-r"><h2 className="text-xl font-semibold">{t("sources")}</h2><p className="mt-1 text-sm text-muted-ink">{t("sourceOnly")}</p><div className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto">{eligibleFacts.map((fact) => <button key={fact.id} disabled={!editable} className="w-full rounded border border-border-strong bg-surface p-3 text-left hover:bg-hover-bg disabled:bg-disabled-bg" onClick={() => insert(fact)}><span className="block font-medium">{String(fact.value)}</span><span className="mt-1 block text-xs text-teal">{fact.evidence ? t("factSource", { document: fact.evidence.documentId, page: fact.evidence.page }) : fact.key}</span></button>)}</div><div className="mt-6 shrink-0 rounded border border-red bg-red-bg p-3"><h3 className="font-semibold text-red">{t("missingInputs")}</h3><p className="mt-1 text-sm">{t("missingInputsBody")}</p><div className="mt-2 text-xs text-red">{missingFacts.map((fact) => fact.key).join(" · ")}</div></div><label className="mt-6 block shrink-0 font-medium">{t("revisionRequest")}<textarea disabled={!editable} className="mt-1 min-h-24 w-full rounded border border-border-strong bg-surface p-3" placeholder={t("revisionPlaceholder")} value={revision} onChange={(event) => setRevision(event.target.value)} /></label><Button disabled={!editable || !revision.trim()} className="mt-2 w-full">{t("requestRevision")}</Button></aside><section className="min-w-0 bg-canvas"><div data-no-print className="sticky top-0 z-10 flex flex-wrap items-center gap-1 border-b border-border bg-surface px-4 py-2" aria-label={t("toolbar")}><IconButton label={t("bold")} disabled={!editable} onClick={() => editor?.chain().focus().toggleBold().run()}><Bold className="size-5" strokeWidth={1.5} /></IconButton><IconButton label={t("italic")} disabled={!editable} onClick={() => editor?.chain().focus().toggleItalic().run()}><Italic className="size-5" strokeWidth={1.5} /></IconButton><IconButton label={t("undo")} disabled={!editable} onClick={() => editor?.chain().focus().undo().run()}><Undo2 className="size-5" strokeWidth={1.5} /></IconButton><IconButton label={t("redo")} disabled={!editable} onClick={() => editor?.chain().focus().redo().run()}><Redo2 className="size-5" strokeWidth={1.5} /></IconButton><Button className="ml-auto" disabled={!editable || !editor} onClick={() => { if (editor) onSave(editor.getJSON() as unknown as EditorDocument); }}><Save className="size-4" strokeWidth={1.5} />{t("saveVersion")}</Button></div><div className="p-4 sm:p-6"><article data-print-surface className="mx-auto min-h-[760px] max-w-[760px] border border-border-strong bg-surface p-8 sm:p-12"><EditorContent editor={editor} /></article></div></section></div>;
}

