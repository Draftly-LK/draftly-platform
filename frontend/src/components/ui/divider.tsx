import { cn } from "@/lib/utils";

/** A 1px rule. Vertical dividers separate side-by-side figures, e.g. a metric row. */
export function Divider({ vertical = false, className }: { vertical?: boolean; className?: string }) {
  return vertical ? (
    <div role="separator" aria-orientation="vertical" className={cn("w-px self-stretch bg-border", className)} />
  ) : (
    <hr className={cn("border-0 border-t border-border", className)} />
  );
}
