import { LocaleToggle } from "./locale-toggle";

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return <div className="flex flex-wrap items-start gap-4 border-b border-border bg-surface px-6 py-5"><div className="min-w-0 flex-1"><h1 className="text-3xl font-semibold">{title}</h1>{description && <p className="mt-1 max-w-3xl text-muted-ink">{description}</p>}</div>{action}<LocaleToggle /></div>;
}

