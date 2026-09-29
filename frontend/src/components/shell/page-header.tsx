import { LocaleToggle } from "./locale-toggle";

/**
 * Page title band shared by every workspace screen: an optional eyebrow, the
 * title in the display serif, a one-line description, and actions on the right.
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
      <div className="flex flex-wrap items-end gap-4 px-6 pb-5 pt-7">
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
          <span data-page-locale>
            <LocaleToggle />
          </span>
        </div>
      </div>
    </div>
  );
}
