import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Nothing here yet. A short heading, one line saying what to do about it, and
 * the action that does it.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  as: Heading = "h2",
  className,
}: {
  icon?: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  as?: "h2" | "h3";
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-start gap-3 py-8", className)}>
      {Icon ? <Icon aria-hidden="true" className="size-6 text-muted-ink" strokeWidth={1.5} /> : null}
      <div>
        <Heading className="text-lg font-semibold text-ink">{title}</Heading>
        {description ? <p className="mt-1 max-w-prose text-sm text-muted-ink">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
