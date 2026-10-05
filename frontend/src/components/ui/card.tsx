import type { ElementType, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const padding = { none: "", md: "p-4", lg: "p-6" } as const;

/**
 * A bordered container on the surface colour: no shadow, no gradient. Use it
 * only where grouping adds meaning, and never put a Card inside a Card; use a
 * Divider or spacing to separate things within one.
 */
export function Card({
  as: Tag = "div",
  pad = "md",
  className,
  ...props
}: HTMLAttributes<HTMLElement> & { as?: ElementType; pad?: keyof typeof padding }) {
  return <Tag className={cn("rounded-card border border-border bg-surface", padding[pad], className)} {...props} />;
}
