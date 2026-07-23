"use client";

import type { JSONContent } from "@tiptap/core";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";

function EditorLoading() {
  const t = useTranslations("devTemplates");
  return (
    <div className="text-muted-ink flex min-h-[480px] items-center justify-center text-sm">
      {t("loadingEditor")}
    </div>
  );
}

const TemplatePreviewEditor = dynamic(
  () => import("./template-preview-editor"),
  {
    ssr: false,
    loading: () => <EditorLoading />,
  },
);

export function TemplatePreviewShell({
  document,
  editable = true,
}: {
  document: JSONContent;
  editable?: boolean;
}) {
  return (
    <article data-print-surface className="template-a4-sheet">
      <TemplatePreviewEditor document={document} editable={editable} />
    </article>
  );
}
