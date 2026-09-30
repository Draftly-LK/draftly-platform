import { HeaderUserButton } from "./user-button";

// The language switcher (LocaleToggle) is hidden until translation works end to end.
// pl-16 below md keeps the title clear of the fixed mobile menu button.
export function PageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return <div className="flex flex-wrap items-start gap-4 border-b border-border bg-surface py-5 pl-16 pr-6 md:pl-6"><div className="min-w-0 flex-1"><h1 className="text-3xl font-semibold">{title}</h1>{description && <p className="mt-1 max-w-3xl text-muted-ink">{description}</p>}</div>{action}<HeaderUserButton /></div>;
}
