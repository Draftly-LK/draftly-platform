import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { TemplatePreviewShell } from "@/components/templates/template-preview-shell";
import { getTemplate } from "@/lib/templates";

export default async function DevTemplatePreviewPage({
  params,
}: {
  params: Promise<{ templateId: string }>;
}) {
  const { templateId } = await params;
  const template = getTemplate(templateId);
  if (!template) notFound();

  const t = await getTranslations("devTemplates");
  const locale = await getLocale();
  const title = locale === "si" ? template.meta.titleSi : template.meta.titleEn;

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 sm:px-6">
      <div data-no-print className="mb-6 flex flex-wrap items-center gap-3">
        <Link
          href="/dev/templates"
          className="text-teal text-sm hover:underline"
        >
          {t("backToList")}
        </Link>
        <span className="text-muted-ink">/</span>
        <h1 className="font-heading text-2xl font-semibold">
          {template.meta.formNumber} — {title}
        </h1>
        <span
          className={
            template.meta.status === "ready"
              ? "border-teal bg-teal-bg text-teal rounded border px-2 py-0.5 text-xs"
              : "border-border-strong bg-hover-bg text-muted-ink rounded border px-2 py-0.5 text-xs"
          }
        >
          {template.meta.status === "ready"
            ? t("statusReady")
            : t("statusStub")}
        </span>
      </div>
      <p data-no-print className="text-muted-ink mb-4 text-sm">
        {t("previewHint")}
      </p>
      <p data-no-print className="mb-4">
        <Link
          href={`/dev/templates/${templateId}/compare`}
          className="text-teal text-sm font-medium hover:underline"
        >
          {t("openCompare")}
        </Link>
      </p>
      <TemplatePreviewShell document={template.document} editable />
    </div>
  );
}
