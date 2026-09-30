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
      <div className="divide-border max-w-3xl divide-y p-6">
        {items.map(({ title, body, icon: Icon }) => (
          <section
            key={title}
            className="grid gap-4 py-6 sm:grid-cols-[40px_1fr]"
          >
            <Icon className="text-forest size-6" strokeWidth={1.5} />
            <div>
              <h2 className="text-2xl font-semibold">{title}</h2>
              <p className="text-muted-ink mt-2">{body}</p>
            </div>
          </section>
        ))}
        <button className="border-border-strong bg-surface hover:bg-hover-bg mt-6 min-h-10 rounded-control border px-3 font-medium">
          {t("contact")}
        </button>
      </div>
    </AppShell>
  );
}
