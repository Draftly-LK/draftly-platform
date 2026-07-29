"use client";

import type { JSONContent } from "@tiptap/core";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";

function textToDoc(text: string): JSONContent {
  const paragraphs = text.split(/\n/).map((line) =>
    line.length === 0
      ? { type: "paragraph" }
      : {
          type: "paragraph",
          content: [{ type: "text", text: line }],
        },
  );
  return {
    type: "doc",
    content: paragraphs.length > 0 ? paragraphs : [{ type: "paragraph" }],
  };
}

function docToText(doc: JSONContent): string {
  const blocks = doc.content ?? [];
  return blocks
    .map((block) => {
      if (!block.content) return "";
      return block.content
        .map((node) => (node.type === "text" ? (node.text ?? "") : ""))
        .join("");
    })
    .join("\n");
}

export default function ExtractionEditor({
  documentId,
  text,
  editable = true,
  onSave,
}: {
  documentId: string;
  text: string;
  editable?: boolean;
  onSave: (text: string) => void;
}) {
  const t = useTranslations("documents");
  const editor = useEditor(
    {
      immediatelyRender: false,
      extensions: [
        StarterKit,
        Placeholder.configure({ placeholder: t("extractionPlaceholder") }),
      ],
      content: textToDoc(text),
      editable,
      editorProps: {
        attributes: {
          class:
            "extraction-prose min-h-[240px] outline-none text-sm leading-relaxed",
        },
      },
    },
    [documentId, editable],
  );

  useEffect(() => {
    if (!editor) return;
    const current = docToText(editor.getJSON());
    if (current !== text) {
      editor.commands.setContent(textToDoc(text), false);
    }
  }, [editor, text]);

  return (
    <div className="border-border-strong overflow-hidden rounded border">
      <div className="border-border flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-sm font-semibold">{t("extractionPreview")}</h3>
        <Button
          type="button"
          variant="primary"
          className="min-h-8 px-2 py-1 text-xs"
          disabled={!editable || !editor}
          onClick={() => {
            if (!editor) return;
            onSave(docToText(editor.getJSON()));
          }}
        >
          <Save className="size-4" strokeWidth={1.5} />
          {t("extractionSave")}
        </Button>
      </div>
      <div className="bg-canvas p-3">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
