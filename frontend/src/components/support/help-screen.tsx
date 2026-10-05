import { BookOpenCheck, LockKeyhole, ShieldQuestion } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export async function HelpScreen() {
  const t = await getTranslations("help");
  const items = [
    { title: t("privacyTitle"), body: t("privacyBody"), icon: LockKeyhole },
    { title: t("workflowTitle"), body: t("workflowBody"), icon: BookOpenCheck },
    {
      title: t("authorityTitle"),
      body: t("authorityBody"),
      icon: ShieldQuestion,
    },
  ];
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="mx-auto w-full max-w-[1240px] p-6">
        <div className="divide-border divide-y">
          {items.map(({ title, body, icon: Icon }) => (
            <section
              key={title}
              className="grid grid-cols-[20px_minmax(0,1fr)] gap-3 py-4 first:pt-0"
            >
              <Icon
                className="text-forest mt-1 size-5"
                strokeWidth={1.5}
                aria-hidden="true"
              />
              <div>
                <h2 className="text-lg font-semibold">{title}</h2>
                <p className="text-muted-ink mt-1 max-w-3xl text-sm">{body}</p>
              </div>
            </section>
          ))}
        </div>
        <button
          type="button"
          className="border-border-strong bg-surface hover:bg-hover-bg rounded-control mt-4 min-h-10 border px-3 font-medium"
        >
          {t("contact")}
        </button>
      </div>
    </AppShell>
  );
}
