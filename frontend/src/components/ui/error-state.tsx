import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A whole region that could not load. Says what happened (`title`), what to do
 * (`children`) and offers the action that does it, usually a retry button.
 */
export function ErrorState({
  title,
  children,
  action,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div role="alert" className={cn("flex flex-col items-start gap-3 py-8", className)}>
      <CircleAlert aria-hidden="true" className="size-6 text-red" strokeWidth={1.5} />
      <div>
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {children ? <p className="mt-1 max-w-prose text-sm text-muted-ink">{children}</p> : null}
      </div>
      {action}
    </div>
  );
}
