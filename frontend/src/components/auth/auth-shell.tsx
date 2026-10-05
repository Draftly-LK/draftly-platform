import { useTranslations } from "next-intl";
import { BrandMark } from "@/components/ui/brand-mark";

/**
 * Sign-in and sign-up layout. From 1024px: a navy brand panel on the left and
 * the form on a light panel on the right. Below that: the brand as a navy band
 * above one column. The form itself is Clerk's, styled by `draftlyAppearance`.
 */
export function AuthShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("auth");
  return (
    <div className="min-h-screen bg-canvas lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside
        data-surface="inverse"
        className="flex flex-col justify-center gap-4 bg-surface-inverse px-6 py-8 text-white lg:min-h-screen lg:gap-6 lg:px-14 lg:py-12"
      >
        <div className="flex items-center gap-3">
          <BrandMark tone="white" className="size-10 shrink-0 lg:size-14" priority />
          <span className="font-display text-3xl font-semibold leading-none">{t("brandName")}</span>
        </div>
        <p className="max-w-sm text-base text-on-dark-muted lg:text-lg">{t("brandLine")}</p>
      </aside>
      <main className="flex items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
        <div className="w-full max-w-md">{children}</div>
      </main>
    </div>
  );
}
