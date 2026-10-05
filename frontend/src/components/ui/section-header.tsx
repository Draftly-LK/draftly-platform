import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Heading for a section of a page: title on the left, one optional action on the right. */
export function SectionHeader({
  title,
  description,
  action,
  as: Heading = "h2",
  id,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  as?: "h2" | "h3";
  id?: string;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        <Heading id={id} className="text-xl font-semibold text-ink">
          {title}
        </Heading>
        {description ? <p className="mt-1 text-sm text-muted-ink">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0 text-sm">{action}</div> : null}
    </div>
  );
}
