"use client";

import dynamic from "next/dynamic";
import type { DraftVersion, EditorDocument, VerifiedFact } from "@/types";

const TiptapEditor = dynamic(() => import("./tiptap-editor"), { ssr: false });

export function EditorShell(props: { version: DraftVersion; facts: VerifiedFact[]; editable: boolean; onSave: (document: EditorDocument) => void }) {
  return <TiptapEditor {...props} />;
}

