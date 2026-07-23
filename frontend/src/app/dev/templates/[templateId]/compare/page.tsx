import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { TemplatePreviewShell } from "@/components/templates/template-preview-shell";
import "@/components/templates/template-form.css";
import { getTemplate } from "@/lib/templates";
import { templatePdfPages } from "@/lib/templates/pdf-pages";

export default async function DevTemplateComparePage({
  params,
}: {
  params: Promise<{ templateId: string }>;
}) {
  if (process.env.NODE_ENV !== "development") notFound();

  const { templateId } = await params;
  const template = getTemplate(templateId);
  if (!template) notFound();

  const pages = templatePdfPages[templateId] ?? [];

  const t = await getTranslations("devTemplates");
  const locale = await getLocale();
  const title = locale === "si" ? template.meta.titleSi : template.meta.titleEn;

  return (
    <div className="mx-auto max-w-[1600px] px-3 py-4 sm:px-4">
      <div data-no-print className="mb-4 flex flex-wrap items-center gap-3">
        <Link
          href="/dev/templates"
          className="text-teal text-sm hover:underline"
        >
          {t("backToList")}
        </Link>
        <span className="text-muted-ink">/</span>
        <Link
          href={`/dev/templates/${templateId}`}
          className="text-teal text-sm hover:underline"
        >
          {template.meta.formNumber}
        </Link>
        <span className="text-muted-ink">/</span>
        <h1 className="font-heading text-xl font-semibold">
          {t("compareTitle")}
        </h1>
      </div>
      <p data-no-print className="text-muted-ink mb-4 text-sm">
        {t("compareHint", { form: `${template.meta.formNumber} — ${title}` })}
      </p>

      <div className="template-compare-layout">
        <section>
          <h2 data-no-print className="font-heading mb-2 text-lg font-semibold">
            {t("comparePdf")}
          </h2>
          <div className="space-y-3">
            {pages.map((page) => {
              const name = `page-${String(page).padStart(2, "0")}.png`;
              return (
                <figure key={page} className="template-compare-pdf">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/dev/form-pages/${name}`}
                    alt={`PDF page ${page}`}
                  />
                  <figcaption
                    data-no-print
                    className="border-border text-muted-ink border-t px-2 py-1 text-xs"
                  >
                    PDF p.{page}
                  </figcaption>
                </figure>
              );
            })}
          </div>
        </section>
        <section>
          <h2 data-no-print className="font-heading mb-2 text-lg font-semibold">
            {t("compareLive")}
          </h2>
          <TemplatePreviewShell document={template.document} editable />
        </section>
      </div>
    </div>
  );
}
