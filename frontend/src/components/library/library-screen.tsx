import { BookOpen, Landmark, Library, MessageSquareText } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export async function LibraryScreen() {
  const t = await getTranslations("library");
  const sources = [
    {
      title: t("titleStatute"),
      type: t("statutes"),
      ref: "SYN-RTA-REF-01",
      icon: BookOpen,
      state: t("verified"),
      verified: true,
    },
    {
      title: t("titleGazette"),
      type: t("gazettes"),
      ref: "SYN-GAZ-02",
      icon: Landmark,
      state: t("verified"),
      verified: true,
    },
    {
      title: t("titleCase"),
      type: t("caseRules"),
      ref: "SYN-CASE-03",
      icon: Library,
      state: t("candidate"),
      verified: false,
    },
    {
      title: t("titleQuestions"),
      type: t("questions"),
      ref: "SYN-QSET-01",
      icon: MessageSquareText,
      state: t("verified"),
      verified: true,
    },
  ];
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="flex flex-wrap gap-3">
          <input
            aria-label={t("search")}
            className="border-border-strong bg-surface h-10 min-w-64 flex-1 rounded border px-3"
            placeholder={t("search")}
          />
          <select
            aria-label={t("all")}
            className="border-border-strong bg-surface h-10 rounded border px-3"
          >
            <option>{t("all")}</option>
            <option>{t("statutes")}</option>
            <option>{t("gazettes")}</option>
            <option>{t("caseRules")}</option>
            <option>{t("questions")}</option>
          </select>
        </div>
        <div className="divide-border border-border bg-surface mt-5 divide-y border-y">
          {sources.map(({ title, type, ref, icon: Icon, state, verified }) => (
            <article
              key={ref}
              className="grid min-h-20 grid-cols-[auto_1fr_auto] items-center gap-4 px-4"
            >
              <Icon className="text-forest size-5" strokeWidth={1.5} />
              <div>
                <div className="font-heading text-xl font-semibold">
                  {title}
                </div>
                <div className="text-muted-ink text-sm">
                  {type} · {ref}
                </div>
              </div>
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${verified ? "border-forest bg-soft-green text-forest" : "border-amber bg-amber-bg text-amber-text"}`}
              >
                <BookOpen className="size-3.5" />
                {state}
              </span>
            </article>
          ))}
        </div>
        <div className="border-amber bg-amber-bg text-amber-text mt-6 border-l-2 p-4">
          {t("corpusNotice")}
        </div>
      </div>
    </AppShell>
  );
}
