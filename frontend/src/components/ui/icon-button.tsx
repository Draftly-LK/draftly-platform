import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Icon-only control. `label` is required: it is the accessible name and the tooltip. */
export function IconButton({
  label,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-control border border-transparent text-ink hover:border-border hover:bg-hover-bg active:bg-active-bg aria-pressed:bg-selected-bg disabled:cursor-not-allowed disabled:text-disabled-fg [@media(pointer:coarse)]:size-11",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
