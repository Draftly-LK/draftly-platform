"use client";

import type { JSONContent } from "@tiptap/core";
import Placeholder from "@tiptap/extension-placeholder";
import Table from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useTranslations } from "next-intl";
import { LockedBlock } from "@/components/editor/locked-block";
import { FormField } from "./nodes/form-field";
import { FormFieldGrid } from "./nodes/form-field-grid";
import { FormSection } from "./nodes/form-section";
import { OfficeUseBox, OfficeUseColumn } from "./nodes/office-use-box";
import { SignatureBlock } from "./nodes/signature-block";
import "./template-form.css";

export default function TemplatePreviewEditor({
  document,
  editable = true,
}: {
  document: JSONContent;
  editable?: boolean;
}) {
  const t = useTranslations("devTemplates");
  const editor = useEditor(
    {
      immediatelyRender: false,
      extensions: [
        StarterKit,
        Placeholder.configure({ placeholder: t("fieldPlaceholder") }),
        FormField,
        FormFieldGrid,
        FormSection,
        OfficeUseBox,
        OfficeUseColumn,
        SignatureBlock,
        LockedBlock,
        Table.configure({ resizable: false }),
        TableRow,
        TableHeader,
        TableCell,
      ],
      content: document,
      editable,
      editorProps: {
        attributes: {
          class: "template-form-page outline-none",
          "aria-label": t("editorLabel"),
        },
      },
    },
    [document],
  );

  return <EditorContent editor={editor} />;
}
