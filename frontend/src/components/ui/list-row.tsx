import type { LiHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * Put this on the row's primary link. Its ::after covers the whole row, so the
 * entire row is one click target while the markup stays a single real link
 * (keyboard focus, middle-click and screen readers all behave).
 */
export const rowLinkClass =
  "after:absolute after:inset-0 after:content-[''] focus-visible:after:outline focus-visible:after:outline-2 focus-visible:after:outline-ring";

/** Table-row equivalent: apply to `<tr>`. */
export const tableRowClass = "border-b border-border last:border-b-0 hover:bg-hover-bg";

const accents = {
  warning: "before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-amber",
  danger: "before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-red",
} as const;

/** A row in a list. `accent` adds a thin left bar for priority rows; pair it with a status chip, never use it alone. */
export function ListRow({
  accent,
  className,
  ...props
}: LiHTMLAttributes<HTMLLIElement> & { accent?: keyof typeof accents }) {
  return (
    <li
      className={cn(
        "relative flex min-h-14 items-center gap-4 border-b border-border px-4 py-2 last:border-b-0 hover:bg-hover-bg",
        accent && accents[accent],
        className,
      )}
      {...props}
    />
  );
}
