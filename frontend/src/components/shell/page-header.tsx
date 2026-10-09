/**
 * Page title band shared by every workspace screen: an optional eyebrow, the
 * title in the display serif, a one-line description, and actions on the right.
 */
export function PageHeader({
  title,
  description,
  action,
  eyebrow,
  headingLevel = "h1",
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  eyebrow?: string;
  headingLevel?: "h1" | "h2";
}) {
  const Heading = headingLevel;
  return (
    <div data-page-header className="border-border bg-surface border-b">
      {/* pl-16 below lg keeps the title clear of the fixed mobile menu button. */}
      <div className="flex flex-wrap items-center gap-4 py-6 pl-16 pr-6 lg:pl-6">
        {/* A floor on the text's width wraps the actions onto their own line on a phone, instead of squeezing the title. */}
        <div className="min-w-[min(100%,16rem)] flex-1">
          {eyebrow && (
            <p className="text-gold-strong mb-1 text-xs font-semibold">
              {eyebrow}
            </p>
          )}
          <Heading className="font-display text-3xl font-semibold leading-tight">
            {title}
          </Heading>
          {description && (
            <p className="text-muted-ink mt-1.5 max-w-3xl">{description}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">{action}</div>
      </div>
    </div>
  );
}
