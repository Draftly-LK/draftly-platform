import { getTranslations } from "next-intl/server";

/** Shown while a route's server content loads: a centred spinner and one line. */
export default async function Loading() {
  const t = await getTranslations("app");
  return (
    <main
      aria-live="polite"
      aria-busy="true"
      className="text-muted-ink grid min-h-[60vh] place-items-center p-8"
    >
      <div className="flex flex-col items-center gap-3">
        <span
          aria-hidden="true"
          className="border-border border-t-forest size-8 animate-spin rounded-full border-[3px]"
        />
        <p className="text-sm">{t("loading")}</p>
      </div>
    </main>
  );
}
