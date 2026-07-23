import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

export default async function DevLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }

  const t = await getTranslations("devTemplates");

  return (
    <div className="bg-canvas min-h-screen">
      <header
        data-app-chrome
        data-no-print
        className="border-border bg-surface border-b"
      >
        <div className="mx-auto flex max-w-[1100px] items-center gap-4 px-4 py-3 sm:px-6">
          <Link
            href="/dev/templates"
            className="font-heading text-forest text-lg font-semibold hover:underline"
          >
            {t("chromeTitle")}
          </Link>
          <span className="border-amber bg-amber-bg text-amber-text rounded border px-2 py-0.5 text-xs">
            {t("devOnly")}
          </span>
          <span className="text-muted-ink ml-auto text-sm">
            {t("chromeHint")}
          </span>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
