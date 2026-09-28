"use client";

import type { JSONContent } from "@tiptap/core";
import { EditorContent, ReactNodeViewRenderer, useEditor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import { GAZETTE_NODES, GazetteLock, GzSlot } from "@/lib/gazette-forms/schema";
import { SlotView } from "./slot-view";
import "./gazette.css";

const InteractiveSlot = GzSlot.extend({
  addNodeView() {
    return ReactNodeViewRenderer(SlotView, { as: "span" });
  },
});

const EXTENSIONS = [...GAZETTE_NODES, InteractiveSlot, GazetteLock];

/**
 * The printed form, rendered by Tiptap. The editor is not editable and the
 * lock plugin refuses document changes, so the prescribed wording cannot move;
 * the blanks are node views that read and write the shared gazette context.
 *
 * Client-only (imported with `ssr: false`), as Tiptap requires.
 */
export default function GazetteDocument({ document }: { document: JSONContent }) {
  const t = useTranslations("gazette");
  const editor = useEditor(
    {
      immediatelyRender: false,
      editable: false,
      extensions: EXTENSIONS,
      content: document,
      editorProps: {
        attributes: { class: "gz-page", "aria-label": t("documentLabel"), role: "document" },
      },
    },
    [document],
  );
  return <EditorContent editor={editor} />;
}
