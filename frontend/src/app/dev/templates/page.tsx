import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { listTemplates } from "@/lib/templates";

export default async function DevTemplatesIndexPage() {
  const t = await getTranslations("devTemplates");
  const locale = await getLocale();
  const templates = listTemplates();

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 sm:px-6">
      <h1 className="font-heading text-3xl font-semibold">{t("title")}</h1>
      <p className="text-muted-ink mt-2 max-w-2xl">{t("description")}</p>

      <ul className="divide-border border-border-strong bg-surface mt-8 divide-y border">
        {templates.map(({ meta }) => {
          const title = locale === "si" ? meta.titleSi : meta.titleEn;
          return (
            <li
              key={meta.id}
              className="flex flex-wrap items-start gap-3 px-4 py-4 sm:px-5"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium tabular-nums">
                    {meta.formNumber}
                  </span>
                  <span className="text-muted-ink">·</span>
                  <span className="font-heading text-lg">{title}</span>
                  <span
                    className={
                      meta.status === "ready"
                        ? "border-teal bg-teal-bg text-teal rounded border px-2 py-0.5 text-xs"
                        : "border-border-strong bg-hover-bg text-muted-ink rounded border px-2 py-0.5 text-xs"
                    }
                  >
                    {meta.status === "ready"
                      ? t("statusReady")
                      : t("statusStub")}
                  </span>
                </div>
                <p className="text-muted-ink mt-1 text-sm">
                  {meta.descriptionEn}
                </p>
                <p className="text-muted-ink mt-1 font-mono text-xs">
                  {meta.id}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/dev/templates/${meta.id}`}
                  className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
                >
                  {t("openPreview")}
                </Link>
                <Link
                  href={`/dev/templates/${meta.id}/compare`}
                  className="border-border-strong bg-surface hover:bg-hover-bg rounded border px-3 py-2 text-sm font-medium"
                >
                  {t("openCompare")}
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
