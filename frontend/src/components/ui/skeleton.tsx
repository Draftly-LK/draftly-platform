import { cn } from "@/lib/utils";

/** A grey bar that stands in for text while data loads. Still when the user prefers reduced motion. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("rounded bg-active-bg motion-safe:animate-pulse", className)} />;
}

/**
 * Placeholder rows shaped like the real rows (a primary line and a muted line),
 * so the page does not jump when the data arrives. Announces itself once.
 */
export function RowsSkeleton({
  rows = 4,
  label,
  className,
}: {
  rows?: number;
  /** Screen-reader text, e.g. "Loading matters". */
  label: string;
  className?: string;
}) {
  return (
    <div role="status" aria-live="polite" className={className}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex min-h-14 items-center gap-4 border-b border-border px-4 py-3 last:border-b-0">
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="hidden h-6 w-24 rounded-full sm:block" />
          <Skeleton className="h-8 w-16" />
        </div>
      ))}
    </div>
  );
}
