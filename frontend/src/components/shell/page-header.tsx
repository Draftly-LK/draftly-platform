import { HeaderUserButton } from "./user-button";

/**
 * Page title band shared by every workspace screen: an optional eyebrow, the
 * title in the display serif, a one-line description, and actions on the right,
 * ending with the profile button so the header is the only bar above the page.
 */
export function PageHeader({
  title,
  description,
  action,
  eyebrow,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <div data-page-header className="border-border bg-surface border-b">
      {/* pl-16 below md keeps the title clear of the fixed mobile menu button. */}
      <div className="flex flex-wrap items-center gap-4 py-6 pl-16 pr-6 md:pl-6">
        <div className="min-w-0 flex-1">
          {eyebrow && (
            <p className="text-gold-strong mb-1 text-xs font-semibold uppercase tracking-[0.1em]">
              {eyebrow}
            </p>
          )}
          <h1 className="font-display text-[32px] font-semibold leading-tight">{title}</h1>
          {description && <p className="text-muted-ink mt-1.5 max-w-3xl">{description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {action}
          <HeaderUserButton />
        </div>
      </div>
    </div>
  );
}
